#kiểm thử chi tiết từng ca nghiệp vụ (Unit Test)
import inspect
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from ai_pipeline.processors import build_key_concepts as concepts_module
from ai_pipeline.processors import build_quiz as quiz_module
from ai_pipeline.processors import build_summary as summary_module
from ai_pipeline.processors._common import (
    parse_json_response,
    render_prompt,
    validate_schema,
)
from ai_pipeline.processors.build_key_concepts import build_key_concepts
from ai_pipeline.processors.build_quiz import build_quiz
from ai_pipeline.processors.build_summary import build_summary
from ai_pipeline.processors.normalize_transcript import normalize_transcript


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "fixtures"
SCHEMAS = PROJECT_ROOT / "schemas"


def _sample_transcript() -> str:
    raw_data = json.loads((FIXTURES / "transcript_sample.json").read_text("utf-8"))
    return normalize_transcript(raw_data)["full_text"]


def _valid_quiz_question() -> dict:
    return {
        "question": "Which answer is correct?",
        "options": ["A", "B", "C", "D"],
        "correct_answer": "A",
        "explanation": "The transcript states A.",
    }


def test_normalize_transcript_accepts_fixture_and_invalid_json_text():
    normalized = normalize_transcript(
        json.loads((FIXTURES / "transcript_sample.json").read_text("utf-8"))
    )
    assert normalized["word_count"] > 0
    assert normalized["segments"][0] == {
        "start": 0.0,
        "end": 6.4,
        "text": (
            "Cloud computing cung cấp tài nguyên như máy chủ, lưu trữ và cơ sở "
            "dữ liệu qua Internet theo nhu cầu."
        ),
    }

    invalid_json = normalize_transcript("  text\n with   extra spaces  ")
    assert invalid_json["full_text"] == "text with extra spaces"
    assert invalid_json["word_count"] == 4


def test_json_response_parser_accepts_plain_and_fenced_json_rejects_invalid():
    expected = {"questions": []}
    assert parse_json_response(json.dumps(expected)) == expected
    assert parse_json_response(f"```json\n{json.dumps(expected)}\n```") == expected
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_json_response("{invalid")


def test_prompt_missing_or_malformed_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_prompt(
            tmp_path / "missing.txt",
            transcript_text="lecture",
        )

    malformed_prompt = tmp_path / "malformed.txt"
    malformed_prompt.write_text("No transcript placeholder.", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        render_prompt(malformed_prompt, transcript_text="lecture")

    unknown_placeholder = tmp_path / "unknown.txt"
    unknown_placeholder.write_text(
        "{{transcript}} {{unknown}}",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported placeholders"):
        render_prompt(unknown_placeholder, transcript_text="lecture")


def test_prompt_rendering_does_not_rewrite_placeholder_text_in_transcript(tmp_path):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text(
        "Generate {{num_questions}} questions from:\n{{transcript}}",
        encoding="utf-8",
    )
    rendered = render_prompt(
        prompt_path,
        transcript_text="Transcript literally contains {{num_questions}}.",
        replacements={"num_questions": "2"},
    )
    assert rendered == (
        "Generate 2 questions from:\n"
        "Transcript literally contains {{num_questions}}."
    )


def test_summary_and_concepts_fallbacks_are_transcript_grounded_and_schema_valid(
    monkeypatch,
):
    monkeypatch.setattr(
        summary_module,
        "_PROMPT_PATH",
        summary_module._PROMPT_PATH.with_name("missing-summary-prompt.txt"),
    )
    summary = build_summary(
        "Photosynthesis converts light energy into chemical energy. "
        "Chlorophyll absorbs light."
    )
    assert "Photosynthesis" in summary["summary"]
    Draft7Validator(
        json.loads((SCHEMAS / "summary.schema.json").read_text("utf-8"))
    ).validate(summary)

    concepts = build_key_concepts(
        "Photosynthesis is the process of converting light energy. "
        "Chlorophyll absorbs light."
    )
    assert concepts[0]["term"] == "Photosynthesis"
    envelope = {
        "title": "Concepts",
        "summary": "Extracted concepts.",
        "key_concepts": concepts,
    }
    Draft7Validator(
        json.loads((SCHEMAS / "summary.schema.json").read_text("utf-8"))
    ).validate(envelope)


def test_malformed_ai_json_falls_back_for_summary_and_concepts():
    malformed_client = lambda _prompt: "not-json"
    summary = build_summary(
        "A database stores structured information.",
        ai_client=malformed_client,
    )
    concepts = build_key_concepts(
        "A database stores structured information.",
        ai_client=malformed_client,
    )
    assert "database" in summary["summary"]
    assert concepts[0]["definition"] == "A database stores structured information."


def test_quiz_strips_options_before_duplicate_validation():
    question = _valid_quiz_question()
    question["options"] = [" A ", "A", "C", "D"]
    question["correct_answer"] = "A"
    with pytest.raises(ValueError, match="remain distinct"):
        quiz_module._validate_quiz({"questions": [question]})


def test_quiz_correct_answer_must_match_a_stripped_option():
    question = _valid_quiz_question()
    question["correct_answer"] = "Missing"
    with pytest.raises(ValueError, match="exactly match"):
        quiz_module._validate_quiz({"questions": [question]})


def test_quiz_fixture_fallback_requires_relevant_transcript_and_enough_questions():
    with pytest.raises(ValueError, match="does not match this transcript"):
        build_quiz("Photosynthesis converts light energy into chemical energy.")

    with pytest.raises(ValueError, match="contains only 3"):
        build_quiz(_sample_transcript(), num_questions=4)

    quiz = build_quiz(_sample_transcript(), num_questions=2)
    assert len(quiz["questions"]) == 2
    Draft7Validator(
        json.loads((SCHEMAS / "quiz.schema.json").read_text("utf-8"))
    ).validate(quiz)


def test_quiz_ai_count_prompt_and_schema_validation():
    captured_prompt = ""

    def client(prompt: str) -> str:
        nonlocal captured_prompt
        captured_prompt = prompt
        return json.dumps({"questions": [_valid_quiz_question()]})

    quiz = build_quiz(
        "The transcript contains the literal token {{num_questions}}.",
        ai_client=client,
        num_questions=1,
    )
    assert "chính xác 1 câu hỏi trắc nghiệm" in captured_prompt
    assert "literal token {{num_questions}}" in captured_prompt
    assert len(quiz["questions"]) == 1

    with pytest.raises(ValueError, match="exactly 2 questions"):
        build_quiz(
            "Transcript",
            ai_client=client,
            num_questions=2,
        )


def test_summary_and_concepts_ai_json_and_schema_validation():
    summary_data = json.loads((FIXTURES / "summary_sample.json").read_text("utf-8"))
    summary = build_summary(
        "Transcript content.",
        ai_client=lambda _prompt: f"```json\n{json.dumps(summary_data)}\n```",
    )
    validate_schema(summary, SCHEMAS / "summary.schema.json")

    concepts = build_key_concepts(
        "Transcript content.",
        ai_client=lambda _prompt: json.dumps(
            {"key_concepts": summary_data["key_concepts"]}
        ),
    )
    validate_schema(
        {
            "title": "Concepts",
            "summary": "Extracted concepts.",
            "key_concepts": concepts,
        },
        SCHEMAS / "summary.schema.json",
    )


def test_public_signatures_remain_backward_compatible():
    assert list(inspect.signature(normalize_transcript).parameters) == ["raw_data"]
    assert list(inspect.signature(build_summary).parameters) == [
        "transcript_text",
        "ai_client",
        "allow_fallback",
    ]
    assert list(inspect.signature(build_key_concepts).parameters) == [
        "transcript_text",
        "ai_client",
        "allow_fallback",
    ]
    assert list(inspect.signature(build_quiz).parameters) == [
        "transcript_text",
        "ai_client",
        "num_questions",
        "allow_fallback",
    ]
    assert inspect.signature(build_quiz).parameters["num_questions"].default == 3

    for builder in (build_summary, build_key_concepts, build_quiz):
        fallback = inspect.signature(builder).parameters["allow_fallback"]
        assert fallback.kind is inspect.Parameter.KEYWORD_ONLY
        assert fallback.default is True


def test_schema_helper_rejects_invalid_final_output():
    with pytest.raises(ValueError, match="does not match"):
        validate_schema(
            {"questions": []},
            SCHEMAS / "quiz.schema.json",
        )


def test_prompt_missing_causes_transcript_fallback_in_summary_and_concepts(
    monkeypatch,
):
    missing_prompt = Path(__file__).parent / "missing-prompt.txt"
    monkeypatch.setattr(summary_module, "_PROMPT_PATH", missing_prompt)
    monkeypatch.setattr(concepts_module, "_PROMPT_PATH", missing_prompt)

    summary = build_summary("A system stores data.", ai_client=lambda _prompt: "{}")
    concepts = build_key_concepts(
        "A system stores data.",
        ai_client=lambda _prompt: "{}",
    )
    assert summary["summary"] == "A system stores data."
    assert concepts[0]["definition"] == "A system stores data."


def test_quiz_prompt_missing_is_visible_for_configured_ai_client(monkeypatch):
    monkeypatch.setattr(quiz_module, "_PROMPT_PATH", Path("missing-quiz-prompt.txt"))
    with pytest.raises(FileNotFoundError):
        build_quiz(
            "Transcript",
            ai_client=lambda _prompt: json.dumps({"questions": [_valid_quiz_question()]}),
            num_questions=1,
        )
