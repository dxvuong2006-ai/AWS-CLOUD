"""Kiểm tra pipeline cục bộ với adapter giả lập."""

from app.adapters.ai.mock_ai import MockAIAdapter
from app.adapters.transcription.mock_transcriber import MockTranscriber
from app.adapters.transcription.aws_transcribe import process_video_pipeline
from app.models.lesson import Lesson
from app.models.user import User


def test_pipeline_stores_pending_draft_with_timestamps(db_session, quiz_course):
    """Transcript mẫu được chuẩn hóa và lưu cùng nháp chờ duyệt."""
    _, course, sections = quiz_course
    instructor = User(name="Teacher", email="pipe@example.test",
                      role="INSTRUCTOR")
    db_session.add(instructor)
    db_session.flush()
    course.instructor_id = instructor.id
    lesson = Lesson(section_id=sections[0].id, title="Lesson", position=1,
                    status="DRAFT")
    db_session.add(lesson)
    db_session.commit()
    result = process_video_pipeline(
        "sample.mp4", lesson.id, db_session, instructor_id=instructor.id,
        transcriber=MockTranscriber(), ai=MockAIAdapter(),
    )
    assert result["status"] == "REVIEW_REQUIRED"
    db_session.refresh(lesson)
    assert lesson.status == "REVIEW_REQUIRED"
    assert lesson.transcript_json["segments"]
    assert lesson.transcript_json["full_text"] == lesson.transcript_json["text"]
