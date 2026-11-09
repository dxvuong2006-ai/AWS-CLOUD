"""Kiểm thử Lambda học liệu không gọi AWS thật."""

import io
import json
from unittest.mock import Mock

from aws_deploy.lambda_ai_processor import handler
from app.models.flashcard import Flashcard


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


def test_persist_draft_stores_review_and_flashcards(db_session, quiz_course, monkeypatch):
    """Lưu summary, quiz và flashcard trong transaction SQLite."""
    from app import database
    from app.models.flashcard import Flashcard
    from app.models.lesson import Lesson
    from app.models.quiz import Question, Quiz
    from app.models.user import User

    _, course, sections = quiz_course
    instructor = User(name="Teacher", email="lambda-db@example.test",
                      role="INSTRUCTOR")
    db_session.add(instructor)
    db_session.flush()
    course.instructor_id = instructor.id
    lesson = Lesson(section_id=sections[0].id, title="Original",
                    position=1, status="DRAFT")
    db_session.add(lesson)
    db_session.commit()
    lesson_id = lesson.id
    instructor_id = instructor.id
    payload = {
        "lesson_id": lesson_id,
        "review_content": {
            "title": "Cloud", "summary": "Cloud summary",
            "quiz_title": "Cloud quiz",
            "key_concepts": [{"term": "Cloud", "definition": "Dịch vụ"}],
            "questions": [{"question": "Q?", "options": ["A", "B"],
                           "correct_answer": "A", "explanation": "A đúng"}],
        },
        "transcript": {"full_text": "Cloud", "segments": [], "language": "vi"},
        "flashcards": [{"term": "Cloud", "definition": "Dịch vụ",
                        "key_takeaway": "Dùng linh hoạt"}],
    }
    monkeypatch.setattr(database, "SessionLocal", lambda: db_session)
    handler.persist_draft(payload, instructor_id)
    assert db_session.get(Lesson, lesson_id).status == "REVIEW_REQUIRED"
    quiz = db_session.query(Quiz).one()
    assert not quiz.is_approved
    assert db_session.query(Question).count() == 1
    card = db_session.query(Flashcard).one()
    assert not card.is_approved and "Dùng linh hoạt" in card.back


def test_handler_optional_db_write(monkeypatch):
    """Chỉ ghi DB khi bật cờ và có instructor_id."""
    ai = fake_ai()
    monkeypatch.setattr(handler, "BedrockAIAdapter", lambda **kwargs: ai)
    monkeypatch.setenv("AI_PROCESSOR_WRITE_DB", "true")
    save = Mock()
    monkeypatch.setattr(handler, "persist_draft", save)
    result = handler.lambda_handler({
        "lesson_id": 1, "transcript_text": "Cloud", "instructor_id": 5,
    }, None)
    assert result["persisted"] is True
    save.assert_called_once()
