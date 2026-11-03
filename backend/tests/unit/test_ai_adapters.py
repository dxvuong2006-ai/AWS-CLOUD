import json

import pytest

from ai_pipeline.processors.build_key_concepts import build_key_concepts
from ai_pipeline.processors.build_quiz import build_quiz
from ai_pipeline.processors.build_summary import build_summary
from ai_pipeline.processors.normalize_transcript import normalize_transcript
from app.adapters import _fixtures
from app.adapters.ai.base import BaseAIAdapter
from app.adapters.ai.mock_ai import MockAIAdapter
from app.adapters.transcription.mock_transcriber import MockTranscriber


def test_mock_adapters_integrate_with_all_processors():
    transcriber = MockTranscriber()
    raw_transcript = transcriber.transcribe("ignored.mp4", language_code="vi-VN")
    normalized = normalize_transcript(raw_transcript)
    ai_adapter = MockAIAdapter()

    summary = build_summary(normalized["full_text"], ai_adapter)
    concepts = build_key_concepts(normalized["full_text"], ai_adapter)
    quiz = build_quiz(normalized["full_text"], ai_adapter)

    assert len(raw_transcript["segments"]) == 4
    assert len(normalized["segments"]) == 4
    assert normalized["word_count"] > 0
    assert summary["title"]
    assert len(concepts) == 3
    assert len(quiz["questions"]) == 3
    assert transcriber.get_job_status("job-1") == {
        "status": "COMPLETED",
        "job_id": "job-1",
    }


def test_num_questions_flows_through_adapter_and_processor():
    adapter = MockAIAdapter()
    quiz = build_quiz(
        "transcript fixture is independent in explicit mock mode",
        adapter,
        num_questions=2,
    )

    assert len(adapter.generate_quiz("ignored", num_questions=1)["questions"]) == 1
    assert len(quiz["questions"]) == 2
    with pytest.raises(ValueError, match="fixture contains only 3"):
        build_quiz("ignored", adapter, num_questions=4)


def test_processor_keeps_legacy_generate_quiz_client_compatible():
    class LegacyQuizClient:
        def generate_quiz(self, transcript: str) -> dict:
            return MockAIAdapter().generate_quiz(transcript)

    with pytest.raises(ValueError, match="exactly 2 questions"):
        build_quiz("transcript", LegacyQuizClient(), num_questions=2)


def test_mock_ai_adapter_preserves_base_interface():
    adapter = MockAIAdapter()
    assert isinstance(adapter, BaseAIAdapter)
    assert list(adapter.generate_summary("ignored")) == [
        "title",
        "summary",
        "key_concepts",
    ]
    assert isinstance(adapter.extract_key_concepts("ignored"), list)


@pytest.mark.parametrize("filename", ["summary_sample.json", "quiz_sample.json"])
def test_missing_ai_fixture_fails_explicitly(tmp_path, monkeypatch, filename):
    monkeypatch.setattr(_fixtures, "_find_fixture_directory", lambda: tmp_path)

    with pytest.raises(FileNotFoundError):
        if filename == "summary_sample.json":
            MockAIAdapter().generate_summary("ignored")
        else:
            MockAIAdapter().generate_quiz("ignored")


def test_missing_transcript_fixture_fails_explicitly(tmp_path, monkeypatch):
    monkeypatch.setattr(_fixtures, "_find_fixture_directory", lambda: tmp_path)
    with pytest.raises(FileNotFoundError):
        MockTranscriber().transcribe("ignored")


def test_corrupted_fixture_fails_explicitly(tmp_path, monkeypatch):
    monkeypatch.setattr(_fixtures, "_find_fixture_directory", lambda: tmp_path)

    (tmp_path / "summary_sample.json").write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        MockAIAdapter().generate_summary("ignored")

    (tmp_path / "transcript_sample.json").write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        MockTranscriber().transcribe("ignored")

    (tmp_path / "quiz_sample.json").write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        MockAIAdapter().generate_quiz("ignored")


def test_fixture_payload_contracts_are_validated(tmp_path, monkeypatch):
    (tmp_path / "transcript_sample.json").write_text(
        json.dumps({"not_segments": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(_fixtures, "_find_fixture_directory", lambda: tmp_path)

    with pytest.raises(ValueError, match="segments list"):
        MockTranscriber().transcribe("ignored")

    (tmp_path / "quiz_sample.json").write_text(
        json.dumps({"questions": "not a list"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="questions list"):
        MockAIAdapter().generate_quiz("ignored")
