"""Checkpoint policy/persistence/HTTP tests using a disposable in-memory database."""
import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "checkpoint-test-only-secret-" * 3

import unittest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, JSON, MetaData, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import JSONB, dialect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.quizzes import router
from app.dependencies import get_current_user, get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.question import Question
from app.models.quiz import CheckpointRemediation, Quiz, QuizAnswer, QuizAttempt
from app.models.section import Section
from app.models.user import User
from app.schemas.quiz import QuizAttemptSubmitRequest
from app.services import quiz_service as service


class CheckpointFixture:
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool,
                                    connect_args={"check_same_thread": False})
        metadata = MetaData()
        for model in (User, Course, Section, Lesson, Enrollment, Quiz, Question,
                      QuizAttempt, QuizAnswer, LessonProgress, CheckpointRemediation):
            table = model.__table__.to_metadata(metadata)
            # Only the test schema substitutes PostgreSQL JSONB for SQLite JSON.
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()
                    column.server_default = None
            for constraint in list(table.constraints):
                if isinstance(constraint, CheckConstraint) and (
                    "jsonb" in str(constraint.sqltext) or "options_json ?" in str(constraint.sqltext)
                ):
                    table.constraints.remove(constraint)
        metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.db.add_all([User(id=1, name="Student", email="one@test.local", role="STUDENT"),
                         User(id=2, name="Other", email="two@test.local", role="STUDENT"),
                         User(id=3, name="Teacher", email="teacher@test.local", role="INSTRUCTOR")])
        self.db.add_all([Course(id=1, instructor_id=3, title="Cloud", status="PUBLISHED", learning_objectives=[]),
                         Course(id=2, instructor_id=3, title="Other", status="PUBLISHED", learning_objectives=[])])
        self.db.add_all([Section(id=1, course_id=1, title="First", position=1),
                         Section(id=2, course_id=1, title="Next", position=2)])
        self.db.add_all([Enrollment(student_id=1, course_id=1), Enrollment(student_id=2, course_id=1)])
        self.db.add_all([Lesson(id=i, section_id=1 if i < 3 else 2, title=f"Lesson {i}",
                                position=i, status="PUBLISHED", key_concepts_json=[]) for i in (1, 2, 3)])
        self.db.add_all([LessonProgress(student_id=1, lesson_id=i, watched_seconds=95,
                                       completed=i != 2) for i in (1, 2, 3)])
        self.db.add_all([Quiz(id=i, section_id=i, title=f"Quiz {i}", is_approved=True) for i in (1, 2)])
        self.db.add_all([Question(id=i, quiz_id=1, question=f"Question {i}", options_json=["A", "B"],
                                 correct_answer="A", explanation="SECRET explanation", position=i)
                         for i in range(1, 6)])
        self.db.add(Question(id=6, quiz_id=2, question="Next question", options_json=["A", "B"],
                             correct_answer="A", explanation="SECRET", position=1))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def payload(self, count=5, request_id=None, **kwargs):
        return QuizAttemptSubmitRequest(request_id=request_id or uuid4(),
            answers=[dict(question_id=i, selected_answer="A") for i in range(1, count + 1)], **kwargs)

    def assert_status(self, status, call):
        with self.assertRaises(HTTPException) as caught:
            call()
        self.assertEqual(caught.exception.status_code, status)

class CheckpointTests(CheckpointFixture, unittest.TestCase):
    def test_public_quiz_never_contains_answers_or_explanations(self):
        data = service.get_checkpoint(self.db, 1, 1, 1).model_dump(mode="json")
        self.assertEqual(data["passing_score"], "80")
        self.assertNotIn("SECRET", str(data))
        for question in data["questions"]:
            self.assertNotIn("correct_answer", question)
            self.assertNotIn("explanation", question)

    def test_enrollment_publication_current_lesson_and_section_gate(self):
        self.assert_status(403, lambda: service.get_checkpoint(self.db, 1, 1, 2))
        self.assert_status(403, lambda: service.get_checkpoint(self.db, 1, 1, 3))
        self.assert_status(403, lambda: service.get_checkpoint(self.db, 2, 1, 3))
        self.assert_status(403, lambda: service.get_checkpoint(self.db, 1, 2))
        self.db.query(Enrollment).filter_by(student_id=1).delete(); self.db.commit()
        self.assert_status(403, lambda: service.get_checkpoint(self.db, 1, 1))
        self.db.add(Enrollment(student_id=1, course_id=1)); self.db.commit()
        self.db.get(Course, 1).status = "DRAFT"; self.db.commit()
        self.assert_status(403, lambda: service.get_checkpoint(self.db, 1, 1))
        self.db.get(Course, 1).status = "PUBLISHED"
        self.db.get(Quiz, 1).is_approved = False; self.db.commit()
        self.assert_status(404, lambda: service.get_checkpoint(self.db, 1, 1))

    def test_grade_omissions_history_and_unlock_are_persisted(self):
        result = service.submit_attempt(self.db, 1, 1, self.payload(4, lesson_id=1))
        self.assertEqual(result.score, Decimal("80.00")); self.assertTrue(result.passed)
        self.assertEqual(len(result.answers), 5)
        self.assertFalse(result.answers[-1].is_correct)
        self.assertIsNone(result.answers[-1].selected_answer)
        self.db.expire_all()
        self.assertEqual(service.attempt_history(self.db, 1, 1)[0].id, result.id)
        self.assertEqual(service.attempt_history(self.db, 1, 2), [])
        self.assertEqual(service.get_checkpoint(self.db, 2, 1, 3).id, 2)
        self.assertEqual(service.get_checkpoint(self.db, 1, 1).attempt_count, 1)

    def test_invalid_duplicate_and_foreign_answers_never_create_attempts(self):
        for answers in ([{"question_id": 6, "selected_answer": "A"}],
                        [{"question_id": 1, "selected_answer": "not an option"}]):
            payload = QuizAttemptSubmitRequest(request_id=uuid4(), answers=answers)
            self.assert_status(422, lambda: service.submit_attempt(self.db, 1, 1, payload))
        with self.assertRaises(ValidationError):
            QuizAttemptSubmitRequest(request_id=uuid4(), answers=[{"question_id": 1}] * 2)
        with self.assertRaises(ValidationError):
            QuizAttemptSubmitRequest(request_id=uuid4(), score=100, answers=[])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(QuizAttempt)), 0)

    def test_same_request_replays_even_after_low_score_blocks_retry(self):
        payload = self.payload(0)
        first = service.submit_attempt(self.db, 1, 1, payload)
        replay = service.submit_attempt(self.db, 1, 1, payload)
        self.assertEqual(first.id, replay.id); self.assertEqual(first.attempt_number, replay.attempt_number)
        self.assertFalse(replay.can_retry); self.assertTrue(replay.remediation_required)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(QuizAttempt)), 1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(QuizAnswer)), 5)
        different = self.payload(1, request_id=payload.request_id)
        self.assert_status(409, lambda: service.submit_attempt(self.db, 1, 1, different))

    def test_low_score_requires_all_three_server_review_conditions(self):
        result = service.submit_attempt(self.db, 1, 1, self.payload(2))
        self.assertFalse(result.can_retry)
        self.assert_status(403, lambda: service.submit_attempt(self.db, 1, 1, self.payload()))
        review = self.db.get(CheckpointRemediation, result.id)
        review.explanation_completed = True; review.practice_total = 3; review.practice_correct = 2
        self.db.commit()
        self.assert_status(403, lambda: service.get_checkpoint(self.db, 1, 1))
        review.review_completed = True; review.practice_correct = 1; self.db.commit()
        self.assert_status(403, lambda: service.get_checkpoint(self.db, 1, 1))
        review.practice_correct = 2; self.db.commit()
        result2 = service.submit_attempt(self.db, 1, 1, self.payload())
        self.assertTrue(result2.passed); self.assertEqual(result2.attempt_number, 2)

    def test_medium_score_can_retry_immediately(self):
        first = service.submit_attempt(self.db, 1, 1, self.payload(3))
        self.assertFalse(first.passed); self.assertTrue(first.can_retry)
        second = service.submit_attempt(self.db, 1, 1, self.payload(5))
        self.assertEqual(second.attempt_number, 2); self.assertTrue(second.passed)

    def test_answer_write_failure_rolls_back_entire_attempt(self):
        real_flush = self.db.flush
        count = 0

        def fail_answers(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError("simulated answer write failure")
            return real_flush(*args, **kwargs)

        with patch.object(self.db, "flush", side_effect=fail_answers):
            with self.assertRaisesRegex(RuntimeError, "simulated answer"):
                service.submit_attempt(self.db, 1, 1, self.payload())
        self.assertEqual(self.db.scalar(select(func.count()).select_from(QuizAttempt)), 0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(QuizAnswer)), 0)

    def test_history_retry_permission_respects_withdrawn_approval(self):
        service.submit_attempt(self.db, 1, 1, self.payload())
        self.db.get(Quiz, 1).is_approved = False
        self.db.commit()
        result = service.attempt_history(self.db, 1, 1)[0]
        self.assertTrue(result.passed)
        self.assertFalse(result.can_retry)
        self.assertFalse(result.remediation_required)

    def test_postgres_lock_and_database_request_uniqueness(self):
        sql = str(select(User).where(User.id == 1).with_for_update().compile(dialect=dialect()))
        self.assertIn("FOR UPDATE", sql)
        payload = self.payload()
        result = service.submit_attempt(self.db, 1, 1, payload)
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError):
            self.db.execute(text("INSERT INTO quiz_attempts (student_id,quiz_id,score,passed,attempt_number,request_id) "
                                 "VALUES (1,1,100,1,2,:key)"), {"key": str(payload.request_id)})
            self.db.commit()
        self.db.rollback()
        self.assertEqual(service.attempt_history(self.db, 1, 1)[0].id, result.id)


class CheckpointHttpTests(CheckpointFixture, unittest.IsolatedAsyncioTestCase):
    async def test_http_auth_payload_and_double_submit(self):
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            self.assertEqual((await client.get("/sections/1/quiz")).status_code, 401)
            app.dependency_overrides[get_current_user] = lambda: self.db.get(User, 3)
            self.assertEqual((await client.get("/sections/1/quiz")).status_code, 403)
            app.dependency_overrides[get_current_user] = lambda: self.db.get(User, 1)
            response = await client.get("/sections/1/quiz?lesson_id=1")
            self.assertEqual(response.status_code, 200); self.assertNotIn("SECRET", response.text)
            missing_key = await client.post("/quizzes/1/attempts", json={"answers": []})
            self.assertEqual(missing_key.status_code, 422)
            payload = self.payload().model_dump(mode="json")
            first = await client.post("/quizzes/1/attempts", json=payload)
            second = await client.post("/quizzes/1/attempts", json=payload)
            self.assertEqual(first.status_code, 200); self.assertEqual(second.json()["id"], first.json()["id"])
            self.assertEqual(len((await client.get("/quizzes/1/attempts")).json()), 1)
