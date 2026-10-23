import json
import logging
import re
from pathlib import Path
from typing import Any


_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "quiz_generation.txt"
_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "quiz_sample.json"
logger = logging.getLogger(__name__)


def _extract_response(response: Any) -> Any:
    if isinstance(response, (dict, list)):
        return response
    if isinstance(response, str):
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return response


def _validate_quiz(response: Any, *, expected_count: int | None = None) -> dict:
    result = _extract_response(response)
    if not isinstance(result, dict) or set(result) != {"questions"}:
        raise ValueError("Quiz output must contain only a questions array.")

    questions = result["questions"]
    if not isinstance(questions, list) or not questions:
        raise ValueError("Quiz output must contain at least one question.")
    if expected_count is not None and len(questions) != expected_count:
        raise ValueError(f"Quiz output must contain exactly {expected_count} questions.")

    validated_questions = []
    for item in questions:
        if not isinstance(item, dict) or set(item) != {
            "question",
            "options",
            "correct_answer",
            "explanation",
        }:
            raise ValueError("Each question must contain only the schema properties.")

        question = item["question"]
        options = item["options"]
        correct_answer = item["correct_answer"]
        explanation = item["explanation"]
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question text must be a non-empty string.")
        if (
            not isinstance(options, list)
            or len(options) != 4
            or any(
                not isinstance(option, str) or not option.strip()
                for option in options
            )
            or len(set(options)) != 4
        ):
            raise ValueError("Each question must have exactly four distinct options.")
        if not isinstance(correct_answer, str) or correct_answer not in options:
            raise ValueError("Correct answer must exactly match one of the options.")
        if not isinstance(explanation, str) or not explanation.strip():
            raise ValueError("Explanation must be a non-empty string.")

        validated_questions.append(
            {
                "question": question.strip(),
                "options": [option.strip() for option in options],
                "correct_answer": correct_answer.strip(),
                "explanation": explanation.strip(),
            }
        )

    return {"questions": validated_questions}


def _generate_with_client(ai_client: Any, transcript_text: str, prompt: str) -> Any:
    generate_quiz = getattr(ai_client, "generate_quiz", None)
    if callable(generate_quiz):
        return generate_quiz(transcript_text)

    generate = getattr(ai_client, "generate", None)
    if callable(generate):
        return generate(prompt)

    invoke = getattr(ai_client, "invoke", None)
    if callable(invoke):
        return invoke(prompt)

    if callable(ai_client):
        return ai_client(prompt)

    raise TypeError(
        "ai_client must provide generate_quiz, generate, invoke, or __call__."
    )


def _load_fallback(num_questions: int) -> dict:
    with _FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        fixture_data = json.load(fixture_file)
    validated_fixture = _validate_quiz(fixture_data)
    return {"questions": validated_fixture["questions"][:num_questions]}


def build_quiz(
    transcript_text: str,
    ai_client=None,
    num_questions: int = 3,
) -> dict:
    """Generate schema-compatible quiz questions or use the local fixture."""
    if (
        isinstance(num_questions, bool)
        or not isinstance(num_questions, int)
        or num_questions < 1
    ):
        raise ValueError("num_questions must be a positive integer.")

    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.replace("{{transcript}}", transcript_text)
        prompt = prompt.replace("3 câu hỏi", f"{num_questions} câu hỏi")
        prompt = prompt.replace(
            "3 object câu hỏi",
            f"{num_questions} object câu hỏi",
        )
        if ai_client is not None:
            response = _generate_with_client(ai_client, transcript_text, prompt)
            return _validate_quiz(response, expected_count=num_questions)
    except Exception as exc:
        logger.warning("AI quiz generation failed; using fixture fallback: %s", exc)

    return _load_fallback(num_questions)


if __name__ == "__main__":
    from normalize_transcript import normalize_transcript

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
