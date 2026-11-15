import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.api.progress import (
    get_course_progress,
    save_lesson_progress,
    start_viewing_session,
)
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.section import Section
from app.models.user import User
from app.schemas.learning import ProgressUpdateRequest

TEST_DATABASE_URL = os.getenv("LEARNCLOUD_TEST_DATABASE_URL")


@pytest.mark.skipif(
    not TEST_DATABASE_URL or "15437" in TEST_DATABASE_URL,
    reason="Requires an isolated PostgreSQL test database, never the local RDS tunnel",
)
def test_progress_schema_is_available_in_isolated_postgres():
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    text(
                        "select table_name from information_schema.tables "
                        "where table_schema = 'public' and table_name in "
                        "('lesson_progress', 'viewing_sessions', 'progress_updates')"
                    )
                )
            }
        assert tables == {"lesson_progress", "viewing_sessions", "progress_updates"}
    finally:
        engine.dispose()


@pytest.mark.skipif(
    not TEST_DATABASE_URL or "15437" in TEST_DATABASE_URL,
    reason="Requires an isolated PostgreSQL test database, never the local RDS tunnel",
)
def test_progress_postgres_idempotency_resume_and_concurrent_sequence():
    engine = create_engine(TEST_DATABASE_URL, pool_size=4, max_overflow=4)
    sessions = sessionmaker(bind=engine, autoflush=False)
    db = sessions()
    db.execute(text("ALTER TABLE courses ADD COLUMN IF NOT EXISTS cover_image TEXT"))
    db.commit()
    student = User(
        cognito_sub=f"progress-{uuid4()}",
        name="Progress Student",
        email=f"progress-{uuid4()}@example.test",
        role="STUDENT",
    )
    instructor = User(
        cognito_sub=f"instructor-{uuid4()}",
        name="Instructor",
        email=f"instructor-{uuid4()}@example.test",
        role="INSTRUCTOR",
    )
    outsider = User(
        cognito_sub=f"outsider-{uuid4()}",
        name="Outsider",
        email=f"outsider-{uuid4()}@example.test",
        role="STUDENT",
    )
    db.add_all([student, instructor, outsider])
    db.flush()
    course = Course(instructor_id=instructor.id, title="Progress PG", status="PUBLISHED")
    db.add(course)
    db.flush()
    section = Section(course_id=course.id, title="Section", position=1)
    db.add(section)
    db.flush()
    lesson = Lesson(
        section_id=section.id,
        title="Lesson",
        position=1,
        status="PUBLISHED",
        duration_seconds=100,
    )
    db.add(lesson)
    db.flush()
    db.add_all(
        [
            Enrollment(student_id=student.id, course_id=course.id),
            Enrollment(student_id=outsider.id, course_id=course.id),
        ]
    )
    db.commit()
    try:
        viewing_session = start_viewing_session(lesson.id, db, student)["id"]
        first_payload = ProgressUpdateRequest(
            last_position_seconds=12.5,
            watched_ranges=[[0, 10]],
            playback_session_id=viewing_session,
            sequence=1,
            request_id=uuid4(),
        )
        first = save_lesson_progress(lesson.id, first_payload, db, student)
        assert save_lesson_progress(lesson.id, first_payload, db, student) == first
        with pytest.raises(HTTPException) as ownership_error:
            save_lesson_progress(lesson.id, first_payload, db, outsider)
        assert ownership_error.value.status_code == 403

        second_payload = first_payload.model_copy(
            update={
                "last_position_seconds": 25.25,
                "watched_ranges": [[5, 25]],
                "sequence": 2,
                "request_id": uuid4(),
            }
        )
        second = save_lesson_progress(lesson.id, second_payload, db, student)
        assert second["watched_seconds"] == 25
        progress = get_course_progress(course.id, db, student)
        assert progress["lessons"][0]["last_position_seconds"] == 25.25
        assert progress["lessons"][0]["watched_ranges"] == [[0, 25]]

        def concurrent_save():
            connection = sessions()
            try:
                return save_lesson_progress(
                    lesson.id,
                    second_payload.model_copy(
                        update={"sequence": 3, "request_id": uuid4()}
                    ),
                    connection,
                    connection.get(User, student.id),
                )
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(concurrent_save) for _ in range(2)]
            outcomes = [future.exception() for future in results]
        assert sum(error is None for error in outcomes) == 1
        assert sum(getattr(error, "status_code", None) == 409 for error in outcomes) == 1

        lesson.duration_seconds = None
        db.commit()
        unknown_duration = get_course_progress(course.id, db, student)
        assert unknown_duration["lessons"][0]["progress_percent"] == 0
        assert unknown_duration["lessons"][0]["completed"] is False

        lesson.duration_seconds = 0
        db.commit()
        zero_duration = get_course_progress(course.id, db, student)
        assert zero_duration["lessons"][0]["completed"] is False

        lesson.duration_seconds = 200
        db.commit()
        backfilled_duration = get_course_progress(course.id, db, student)
        assert backfilled_duration["lessons"][0]["progress_percent"] == 12.5
        assert backfilled_duration["lessons"][0]["completed"] is True
        assert backfilled_duration["overall_percent"] == 100.0
    finally:
        db.rollback()
        db.close()
        engine.dispose()
