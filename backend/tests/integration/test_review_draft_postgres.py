"""Review draft persistence against a dedicated loopback PostgreSQL test DB only."""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.database import Base
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.section import Section
from app.models.user import User
from app.schemas.review import DraftGeneration, DraftUpdate
from app.services import review_service
from app.adapters.ai.mock_ai import MockAIAdapter


def _test_engine():
    value = os.environ.get("LEARNCLOUD_REVIEW_TEST_DATABASE_URL", "")
    if not value:
        pytest.skip("Dedicated PostgreSQL review test URL is not configured.")
    url = make_url(value)
    if (
        url.get_backend_name() not in {"postgresql", "postgresql+psycopg2"}
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.port != 15438
        or url.database != "learncloud_review_test"
        or url.username != "learncloud_review_test"
        or url.query
    ):
        raise RuntimeError("Refusing non-isolated review PostgreSQL test URL.")
    return create_engine(url, hide_parameters=True)


def test_review_save_commit_reload_and_partial_patch_on_postgresql():
    engine = _test_engine()
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            instructor = User(
                name="Review Instructor", email="review@example.test",
                role="INSTRUCTOR",
            )
            student = User(
                name="Review Student", email="student-review@example.test",
                role="STUDENT",
            )
            db.add_all([instructor, student])
            db.flush()
            course = Course(
                instructor_id=instructor.id, title="Review test", status="PUBLISHED",
            )
            db.add(course)
            db.flush()
            section = Section(course_id=course.id, title="Review", position=1)
            db.add(section)
            db.flush()
            lesson = Lesson(
                section_id=section.id, title="Draft", position=1, status="DRAFT",
            )
            db.add(lesson)
            db.commit()
            lesson_id = lesson.id
            instructor_id = instructor.id

            draft = review_service.generate_draft(
                db, lesson_id=lesson_id, instructor_id=instructor_id,
                payload=DraftGeneration(transcript="Cloud service transcript."),
                ai=MockAIAdapter(),
            )
            lesson.processed_video_key = f"lessons/{lesson_id}/processed/video.mp4"
            db.commit()

            payload = draft.model_dump(include={
                "title", "summary", "key_concepts", "flashcards",
                "quiz_title", "questions",
            })
            payload["flashcards"].append({
                "front": "Manual card", "back": "Manual answer",
                "position": len(payload["flashcards"]) + 1,
            })
            payload["questions"].append({
                "question": "Manual question?", "options": ["Yes", "No"],
                "correct_answer": "Yes", "explanation": "Verified.",
            })
            saved = review_service.update_draft(
                db, lesson_id=lesson_id, instructor_id=instructor_id,
                payload=DraftUpdate(**payload, expected_revision=draft.revision),
            )
            db.close()

        # A fresh connection/session proves the data was committed to PostgreSQL.
        with Session(engine) as reloaded_session:
            reloaded = review_service.get_draft(
                reloaded_session, lesson_id=lesson_id,
                instructor_id=instructor_id,
            )
            assert reloaded.flashcards == saved.flashcards
            assert reloaded.questions == saved.questions
            cards_before = reloaded.flashcards
            questions_before = reloaded.questions
            partial = review_service.update_draft(
                reloaded_session, lesson_id=lesson_id,
                instructor_id=instructor_id,
                payload=DraftUpdate(
                    **{
                        **reloaded.model_dump(include={
                            "title", "summary", "key_concepts", "flashcards",
                            "quiz_title", "questions",
                        }),
                        "summary": "PostgreSQL partial summary edit.",
                    },
                    expected_revision=reloaded.revision,
                ),
            )
            assert partial.flashcards == cards_before
            assert partial.questions == questions_before
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
