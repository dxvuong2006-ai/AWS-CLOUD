import json
import logging
from pathlib import Path
from typing import Any

if __package__:
    from ._common import (
        call_ai_client,
        clean_text,
        meaningful_words,
        parse_json_response,
        render_prompt,
        validate_schema,
    )
    from .normalize_transcript import normalize_transcript
else:
    from _common import (
        call_ai_client,
        clean_text,
        meaningful_words,
        parse_json_response,
        render_prompt,
        validate_schema,
    )
    from normalize_transcript import normalize_transcript


_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "quiz_generation.txt"
)
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "quiz_sample.json"
)
_TRANSCRIPT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "transcript_sample.json"
)
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "quiz.schema.json"
)
logger = logging.getLogger(__name__)


def _validate_quiz(
    response: Any, *, expected_count: int | None = None
) -> dict:
    result = parse_json_response(response)
    if not isinstance(result, dict) or set(result) != {"questions"}:
        raise ValueError("Quiz output must contain only a questions array.")

    questions = result["questions"]
    if not isinstance(questions, list) or not questions:
        raise ValueError("Quiz output must contain at least one question.")
    if expected_count is not None and len(questions) != expected_count:
        raise ValueError(
            f"Quiz output must contain exactly {expected_count} questions."
        )

    validated_questions = []
    for item in questions:
        if not isinstance(item, dict) or set(item) != {
            "question",
            "options",
            "correct_answer",
            "explanation",
        }:
            raise ValueError(
                "Each question must contain only the schema properties."
            )

        question = clean_text(item["question"])
        options = item["options"]
        correct_answer = clean_text(item["correct_answer"])
        explanation = clean_text(item["explanation"])
        if not question:
            raise ValueError("Question text must be a non-empty string.")
        if (
            not isinstance(options, list)
            or len(options) != 4
            or any(
                not isinstance(option, str) or not option.strip()
                for option in options
            )
        ):
            raise ValueError(
                "Each question must have exactly four non-empty options."
            )

        normalized_options = [clean_text(option) for option in options]
        if len(set(normalized_options)) != 4:
            raise ValueError(
                "Question options must remain distinct after trimming."
            )
        if not correct_answer or correct_answer not in normalized_options:
            raise ValueError(
                "Correct answer must exactly match one of the options."
            )
        if not explanation:
            raise ValueError("Explanation must be a non-empty string.")

        validated_questions.append(
            {
                "question": question,
                "options": normalized_options,
                "correct_answer": correct_answer,
                "explanation": explanation,
            }
        )

    return validate_schema({"questions": validated_questions}, _SCHEMA_PATH)


def _fixture_matches_transcript(transcript_text: str) -> bool:
    with _TRANSCRIPT_FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        source_fixture = json.load(fixture_file)
    source_text = normalize_transcript(source_fixture)["full_text"]
    source_words = meaningful_words(source_text)
    transcript_words = meaningful_words(transcript_text)
    if not source_words:
        return False
    return len(source_words & transcript_words) / len(source_words) >= 0.5


def _load_fallback(transcript_text: str, num_questions: int) -> dict:
    if not _fixture_matches_transcript(transcript_text):
        raise ValueError(
            "No AI client is configured and the local quiz fixture does not "
            "match this transcript. Configure an AI client to generate a "
            "transcript-specific quiz."
        )

    with _FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        fixture_data = json.load(fixture_file)
    validated_fixture = _validate_quiz(fixture_data)
    available = len(validated_fixture["questions"])
    if num_questions > available:
        raise ValueError(
            f"Requested {num_questions} questions, but the local quiz fixture "
            f"contains only {available}."
        )
    return {"questions": validated_fixture["questions"][:num_questions]}


def build_quiz(
    transcript_text: str,
    ai_client=None,
    num_questions: int = 3,
) -> dict:
    (
        "Generate a Draft-07-valid quiz or use a matching local "
        "development fixture."
    )
    if (
        isinstance(num_questions, bool)
        or not isinstance(num_questions, int)
        or num_questions < 1
    ):
        raise ValueError("num_questions must be a positive integer.")

    if ai_client is not None:
        prompt = render_prompt(
            _PROMPT_PATH,
            transcript_text=transcript_text,
            replacements={"num_questions": str(num_questions)},
        )
        response = call_ai_client(
            ai_client,
            prompt=prompt,
            transcript_text=transcript_text,
            transcript_methods=("generate_quiz",),
            transcript_method_kwargs={"num_questions": num_questions},
        )
        return _validate_quiz(response, expected_count=num_questions)

    logger.info(
        "No AI client configured; using the local development quiz fixture."
    )
    return _load_fallback(transcript_text, num_questions)


if __name__ == "__main__":
    transcript_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "transcript_sample.json"
    )
    if transcript_path.exists():
        with transcript_path.open(encoding="utf-8") as transcript_file:
            transcript_data = json.load(transcript_file)
        normalized = normalize_transcript(transcript_data)
        quiz = build_quiz(normalized["full_text"])
        print(len(quiz["questions"]))
    else:
        print(f"Transcript fixture not found: {transcript_path}")
