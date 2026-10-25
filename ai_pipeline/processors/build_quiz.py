import json
import logging
from pathlib import Path
from typing import Any

if __package__:
    from ._common import (
        AIClientError,
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
        AIClientError,
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
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "quiz.schema.json"
)
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "quiz_sample.json"
)
_TRANSCRIPT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "transcript_sample.json"
)
logger = logging.getLogger(__name__)


def _validate_quiz(
    response: Any, *, expected_count: int | None = None
) -> dict:
    """Return normalized quiz data; reject invalid fields or expected_count."""
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


def _load_fallback(transcript_text: str, num_questions: int) -> dict:
    """Return validated local samples when the legacy relevance check passes.

    This development fallback uses lexical overlap, not semantic grounding.
    Reject unrelated transcripts and requests exceeding the fixture size.
    """
    with _TRANSCRIPT_FIXTURE_PATH.open(encoding="utf-8") as source_file:
        source = normalize_transcript(json.load(source_file))["full_text"]
    source_words = meaningful_words(source)
    transcript_words = meaningful_words(transcript_text)
    if (
        not source_words
        or len(source_words & transcript_words) / len(source_words) < 0.5
    ):
        raise ValueError(
            "The local quiz fixture does not match this transcript. "
            "Configure an AI client for transcript-specific questions."
        )
    with _FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        quiz = _validate_quiz(json.load(fixture_file))
    available = len(quiz["questions"])
    if num_questions > available:
        raise ValueError(
            f"Requested {num_questions} questions, but the quiz fixture "
            f"contains only {available}."
        )
    logger.warning(
        "build_quiz source=fixture; reason=no AI client configured; "
        "development fallback, not AI-generated content"
    )
    return {"questions": quiz["questions"][:num_questions]}


def build_quiz(
    transcript_text: str,
    ai_client: Any = None,
    num_questions: int = 3,
    *,
    allow_fallback: bool = True,
) -> dict:
    """Return a validated quiz with optional legacy local fixture fallback.

    transcript_text supplies content; num_questions is a positive count.
    allow_fallback defaults to True for compatibility with local callers.
    Set it to False in production to prohibit fixture access. A configured
    client's errors always propagate instead of substituting sample content.
    Declared provider failures raise AIClientError; invalid responses raise
    ValueError. The development fixture is never loaded with a client set.
    """
    if (
        isinstance(num_questions, bool)
        or not isinstance(num_questions, int)
        or num_questions < 1
    ):
        raise ValueError("num_questions must be a positive integer.")
    if ai_client is None:
        if not allow_fallback:
            raise AIClientError("An AI client is required in strict mode.")
        return _load_fallback(transcript_text, num_questions)
    if not clean_text(transcript_text):
        raise ValueError("transcript_text must be a non-empty string.")
    prompt = render_prompt(
        _PROMPT_PATH,
        transcript_text=transcript_text,
        replacements={"num_questions": str(num_questions)},
    )
    try:
        response = call_ai_client(
            ai_client,
            prompt=prompt,
            transcript_text=transcript_text,
            transcript_methods=("generate_quiz",),
            transcript_method_kwargs={"num_questions": num_questions},
        )
    except (AIClientError, TimeoutError, ConnectionError) as exc:
        raise AIClientError("AI quiz generation failed.") from exc
    return _validate_quiz(response, expected_count=num_questions)
