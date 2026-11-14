import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.question import Question
from app.models.quiz import Quiz, QuizAttempt
from app.models.section import Section
from app.models.user import User
from app.schemas.quiz import QuizSubmitRequest
from app.services import quiz_service


TEST_DATABASE_URL = os.getenv("LEARNCLOUD_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or "15437" in TEST_DATABASE_URL,
    reason="Requires an isolated PostgreSQL test database, never the local RDS tunnel",
)


def _fixture(db):
    db.execute(text("ALTER TABLE courses ADD COLUMN IF NOT EXISTS cover_image TEXT"))
    db.commit()
    student = User(
        cognito_sub=f"quiz-student-{uuid4()}",
        name="Quiz Student",
        email=f"quiz-student-{uuid4()}@example.test",
        role="STUDENT",
    )
    instructor = User(
        cognito_sub=f"quiz-instructor-{uuid4()}",
        name="Quiz Instructor",
        email=f"quiz-instructor-{uuid4()}@example.test",
        role="INSTRUCTOR",
    )
    db.add_all([student, instructor])
    db.flush()
    course = Course(
        instructor_id=instructor.id,
        title="Quiz Flow",
        status="PUBLISHED",
    )
    db.add(course)
    db.flush()
    first = Section(course_id=course.id, title="No Checkpoint", position=1)
    second = Section(course_id=course.id, title="Checkpoint", position=2)
    db.add_all([first, second])
    db.flush()
    lesson = Lesson(
        section_id=second.id,
        title="Completed Lesson",
        position=1,
        status="PUBLISHED",
        duration_seconds=100,
    )
    db.add(lesson)
    db.add(Enrollment(student_id=student.id, course_id=course.id))
    db.flush()
    db.add(LessonProgress(
        student_id=student.id,
        lesson_id=lesson.id,
        watched_seconds=100,
        completed=True,
    ))
    quiz = Quiz(
        section_id=second.id,
        title="Checkpoint",
        is_approved=True,
    )
    db.add(quiz)
    db.flush()
    db.add(Question(
        quiz_id=quiz.id,
        question="Correct?",
        options_json=["A", "B"],
        correct_answer="A",
        position=1,
    ))
    db.commit()
    return student, course, first, second, quiz


def test_postgres_checkpoint_flow_and_idempotent_concurrent_submit():
    engine = create_engine(TEST_DATABASE_URL, pool_size=4, max_overflow=4)
    sessions = sessionmaker(bind=engine, autoflush=False)
    db = sessions()
    try:
        student, course, first, second, quiz = _fixture(db)
        checkpoint = quiz_service.get_checkpoint(
            db, second.id, student.id
        )
        assert checkpoint.id == quiz.id

        request_id = uuid4()
        payload = QuizSubmitRequest(
            request_id=request_id,
            answers=[{"question_id": checkpoint.questions[0].id, "selected_answer": "A"}],
        )

        def submit():
            connection = sessions()
            try:
                return quiz_service.submit_attempt(
                    connection, quiz.id, student.id, payload
                )
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            results = [future.result() for future in futures]
        assert results[0].id == results[1].id
        assert db.query(QuizAttempt).filter_by(
            student_id=student.id, quiz_id=quiz.id
        ).count() == 1
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_postgres_unapproved_previous_checkpoint_blocks_bypass():
    engine = create_engine(TEST_DATABASE_URL)
    sessions = sessionmaker(bind=engine, autoflush=False)
    db = sessions()
    try:
        student, course, first, second, quiz = _fixture(db)
        prior_quiz = Quiz(
            section_id=first.id,
            title="Unapproved checkpoint",
            is_approved=False,
        )
        db.add(prior_quiz)
        db.commit()
        with pytest.raises(HTTPException) as error:
            quiz_service.get_checkpoint(db, second.id, student.id)
        assert error.value.status_code == 403
    finally:
        db.rollback()
        db.close()
        engine.dispose()