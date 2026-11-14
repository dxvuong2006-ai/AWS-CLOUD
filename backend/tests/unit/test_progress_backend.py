from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.progress import save_lesson_progress, start_viewing_session
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.section import Section
from app.schemas.learning import ProgressUpdateRequest
from app.models.user import User


def _lesson(db_session):
    student = User(
        cognito_sub="progress-student",
        name="Progress Student",
        email="progress@example.test",
        role="STUDENT",
    )
    db_session.add(student)
    db_session.flush()
    course = Course(instructor_id=student.id, title="Progress", status="PUBLISHED")
    db_session.add(course)
    db_session.flush()
    section = Section(course_id=course.id, title="Section", position=1)
    db_session.add(section)
    db_session.flush()
    lesson = Lesson(
        section_id=section.id,
        title="Lesson",
        position=1,
        status="PUBLISHED",
        duration_seconds=100,
    )
    db_session.add(lesson)
    db_session.flush()
    db_session.add(Enrollment(student_id=student.id, course_id=course.id))
    db_session.commit()
    return student, lesson


def test_progress_contract_accepts_viewing_metadata():
    payload = ProgressUpdateRequest(
        last_position_seconds=0.205447,
        watched_ranges=[[0.000648, 0.205447]],
        playback_session_id=uuid4(),
        sequence=1,
        request_id=uuid4(),
    )
    assert payload.sequence == 1


def test_progress_requires_session_and_is_idempotent(db_session):
    student, lesson = _lesson(db_session)
    session = start_viewing_session(lesson.id, db_session, student)["id"]
    request_id = uuid4()
    payload = ProgressUpdateRequest(
        last_position_seconds=20.5,
        watched_ranges=[[0, 10]],
        playback_session_id=session,
        sequence=1,
        request_id=request_id,
    )

    first = save_lesson_progress(lesson.id, payload, db_session, student)
    retry = save_lesson_progress(lesson.id, payload, db_session, student)

    assert first == retry
    progress = db_session.query(LessonProgress).one()
    assert progress.watched_seconds == 10
    assert progress.last_position_seconds == 20.5

    second = save_lesson_progress(
        lesson.id,
        payload.model_copy(
            update={
                "sequence": 2,
                "request_id": uuid4(),
                "watched_ranges": [[5, 15]],
                "last_position_seconds": 15.25,
            }
        ),
        db_session,
        student,
    )
    assert second["watched_seconds"] == 15
    assert second["watched_ranges"] == [[0, 15]]

    with pytest.raises(HTTPException) as exc_info:
        save_lesson_progress(
            lesson.id,
            payload.model_copy(update={"sequence": 3, "playback_session_id": uuid4()}),
            db_session,
            student,
        )
    assert exc_info.value.status_code == 403
