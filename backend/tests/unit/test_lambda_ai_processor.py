"""Kiểm thử Lambda học liệu không gọi AWS thật."""

import io
import json
from unittest.mock import Mock

from aws_deploy.lambda_ai_processor import handler


def fake_ai():
    """Tạo adapter AI trả học liệu phù hợp."""
    ai = Mock()
    ai.used_fallback = False
    ai.generate_summary.return_value = {"title": "Cloud", "summary": "S",
                                        "key_concepts": []}
    ai.extract_key_concepts.return_value = [
        {"term": "Cloud", "definition": "Dịch vụ tính toán"}]
    ai.generate_quiz.return_value = {"questions": [{"question": "Q"}]}
    ai._invoke.return_value = json.dumps({"cards": [
        {"term": "Cloud", "key_takeaway": "Triển khai ứng dụng linh hoạt."}
    ]})
    return ai


def test_handler_accepts_text_and_builds_review_payload(monkeypatch):
    """Tạo payload nháp với key_takeaway do AI sinh."""
    ai = fake_ai()
    monkeypatch.setattr(handler, "BedrockAIAdapter", lambda **kwargs: ai)
    result = handler.lambda_handler({"lesson_id": 2,
                                     "transcript_text": "Cloud là dịch vụ."}, None)
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["review_content"]["title"] == "Cloud"
    assert result["review_content"]["questions"] == [{"question": "Q"}]
    assert result["flashcards"][0]["key_takeaway"] == "Triển khai ứng dụng linh hoạt."


def test_flashcard_fallback_is_distinct():
    """Phương án dự phòng không trả định nghĩa nguyên văn."""
    ai = fake_ai()
    ai._invoke.return_value = "{}"
    result = handler.build_flashcards(
        [{"term": "Cloud", "definition": "Dịch vụ tính toán"}], "Cloud", ai)
    assert result[0]["key_takeaway"] == "Ứng dụng cốt lõi: Dịch vụ tính toán"


def test_handler_s3_transcribe_and_closes_stream(monkeypatch):
    """Nhận URI S3 và giữ mốc thời gian Transcribe."""
    ai = fake_ai()
    monkeypatch.setattr(handler, "BedrockAIAdapter", lambda **kwargs: ai)
    stream = io.BytesIO(json.dumps({"results": {"items": [
        {"type": "pronunciation", "start_time": "1", "end_time": "2",
         "alternatives": [{"content": "Cloud"}]}
    ]}}).encode())
    client = Mock()
    client.get_object.return_value = {"Body": stream}
    monkeypatch.setattr(handler.boto3, "client", lambda service: client)
    result = handler.lambda_handler({"lesson_id": 3,
                                     "s3_transcript_uri": "s3://bucket/a.json"}, None)
    assert stream.closed
    assert result["transcript"]["segments"][0]["start"] == 1.0
