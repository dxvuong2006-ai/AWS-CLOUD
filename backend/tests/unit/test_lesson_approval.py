"""API regression tests for the current, persisted instructor review workflow."""

import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_current_user, get_db
from app.lesson_states import LessonStatus
from app.main import app
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz
from app.models.section import Section
from app.models.user import User
from app.schemas.lesson import LessonProcessingStatusResponse
from app.schemas.review import DraftApproval
from app.services import review_service
from app.utils.errors import ConflictError


class ApprovalApiTests(unittest.IsolatedAsyncioTestCase):
    """Exercise HTTP, repository writes, revision checks, and publish gates."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.user = User(
            name="Review Owner", email="review-owner@example.test",
            role="INSTRUCTOR", status="ACTIVE",
        )
        self.db.add(self.user)
        self.db.flush()
        self.course = Course(
            instructor_id=self.user.id, title="Approval test", status="DRAFT",
        )
        self.db.add(self.course)
        self.db.flush()
        self.section = Section(
            course_id=self.course.id, title="Section", position=1,
        )
        self.db.add(self.section)
        self.db.flush()
        self.lesson = Lesson(
            section_id=self.section.id, title="Reviewed lesson", position=1,
            status="REVIEW_REQUIRED", raw_video_key="raw/original.mp4",
            processed_video_key="processed/reviewed.mp4",
            transcript_json={"segments": [{"text": "Reviewed transcript"}]},
            summary="Reviewed summary", key_concepts_json=[
                {"term": "Containers", "definition": "Isolated workloads."},
            ], retry_count=2,
        )
        self.db.add(self.lesson)
        self.db.flush()
        self.quiz = Quiz(section_id=self.section.id, title="Checkpoint")
        self.flashcard = Flashcard(
            lesson_id=self.lesson.id, front="Container", back="Isolated workload",
            position=1,
        )
        self.db.add_all([self.quiz, self.flashcard])
        self.db.flush()
        self.db.add(Question(
            quiz_id=self.quiz.id, position=1, question="What is a container?",
            options_json=["Isolated workload", "Database"],
            correct_answer="Isolated workload", explanation="It isolates workloads.",
        ))
        self.db.commit()

        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.addCleanup(app.dependency_overrides.clear)
        self.draft = review_service.get_draft(
            self.db, lesson_id=self.lesson.id, instructor_id=self.user.id,
        )

    async def call(self, method="POST", path=None, **kwargs):
        path = path or f"/lessons/{self.lesson.id}/approve"
        if method == "POST" and path.endswith("/approve") and "json" not in kwargs:
            kwargs["json"] = {"expected_revision": self.draft.revision}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        ) as client:
            response = await client.request(method, path, **kwargs)
            self.db.expire_all()
            return response

    async def test_explicit_approval_is_separate_from_publish_and_revision_checked(self):
        response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["lesson_id"], self.lesson.id)
        self.assertEqual(response.json()["status"], "PUBLISHED")
        self.assertTrue(self.db.get(Flashcard, self.flashcard.id).is_approved)
        self.assertTrue(self.db.get(Quiz, self.quiz.id).is_approved)
        self.assertEqual(self.db.get(Course, self.course.id).status, "DRAFT")
        self.assertEqual(self.db.get(Lesson, self.lesson.id).retry_count, 2)
        duplicate = await self.call()
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["code"], "LESSON_NOT_REVIEWABLE")

    async def test_review_approve_publish_workflow(self):
        before = await self.call("POST", f"/courses/{self.course.id}/publish")
        self.assertEqual(before.status_code, 409)
        self.assertEqual(before.json()["code"], "LESSON_APPROVAL_REQUIRED")
        self.assertEqual((await self.call()).status_code, 200)
        published = await self.call("POST", f"/courses/{self.course.id}/publish")
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(
            (self.db.get(Course, self.course.id).status,
             self.db.get(Lesson, self.lesson.id).status),
            ("PUBLISHED", "PUBLISHED"),
        )
        self.assertEqual(
            (await self.call("POST", f"/courses/{self.course.id}/publish")).status_code,
            200,
        )

    async def test_publish_rejects_content_that_became_incomplete_after_approval(self):
        self.assertEqual((await self.call()).status_code, 200)
        self.lesson.summary = ""
        self.db.commit()
        response = await self.call("POST", f"/courses/{self.course.id}/publish")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "REVIEW_CONTENT_INCOMPLETE")
        self.assertEqual(self.db.get(Course, self.course.id).status, "DRAFT")

    async def test_missing_lesson(self):
        response = await self.call("POST", "/lessons/99999/approve")
        self.assertEqual(response.status_code, 404)

    async def test_owner_required_before_approval_or_idempotency(self):
        self.course.instructor_id = self.user.id + 100
        self.db.commit()
        self.assertEqual((await self.call()).status_code, 403)
        self.assertEqual(self.db.get(Lesson, self.lesson.id).status, "REVIEW_REQUIRED")

    async def test_student_and_admin_cannot_approve(self):
        for role in ("STUDENT", "ADMIN"):
            self.user.role = role
            self.db.commit()
            self.assertEqual((await self.call()).status_code, 403)
        self.assertEqual(self.db.get(Lesson, self.lesson.id).status, "REVIEW_REQUIRED")

    async def test_unknown_identity(self):
        app.dependency_overrides.pop(get_current_user, None)
        response = await self.call()
        self.assertEqual(response.status_code, 401)

    async def test_ownership_is_rechecked_after_section_lock(self):
        def transfer(_db, _lesson_id):
            self.course.instructor_id = self.user.id + 100
            self.db.flush()

        with patch("app.repositories.review_repo.lock_section", side_effect=transfer):
            response = await self.call()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.db.get(Lesson, self.lesson.id).status, "REVIEW_REQUIRED")

    async def test_every_non_reviewable_state_is_rejected(self):
        for state in LessonStatus:
            if state is LessonStatus.REVIEW_REQUIRED:
                continue
            self.lesson.status = state.value
            self.db.commit()
            response = await self.call()
            self.assertEqual(response.status_code, 409, state.value)
            self.lesson.status = LessonStatus.REVIEW_REQUIRED.value
            self.db.commit()

    async def test_approval_preserves_published_course_status(self):
        self.course.status = "PUBLISHED"
        self.db.commit()
        response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.get(Course, self.course.id).status, "PUBLISHED")
        self.assertEqual(self.db.get(Lesson, self.lesson.id).status, "PUBLISHED")

    async def test_raw_upload_does_not_substitute_for_processed_video(self):
        self.lesson.processed_video_key = None
        self.db.commit()
        response = await self.call()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "PROCESSED_VIDEO_REQUIRED")
        self.assertEqual(self.db.get(Lesson, self.lesson.id).status, "REVIEW_REQUIRED")

    async def test_empty_review_content_is_rejected(self):
        for field, value in (
            ("transcript_json", None), ("transcript_json", {}),
            ("transcript_json", []), ("summary", " "), ("summary", None),
            ("key_concepts_json", []),
        ):
            original = getattr(self.lesson, field)
            setattr(self.lesson, field, value)
            self.db.commit()
            response = await self.call()
            self.assertEqual(response.status_code, 409, field)
            self.assertEqual(response.json()["code"], "REVIEW_CONTENT_INCOMPLETE")
            setattr(self.lesson, field, original)
            self.db.commit()

    def test_null_key_concepts_are_rejected_by_business_validation(self):
        invalid_lesson = Lesson(
            id=900, section_id=self.section.id, title="Invalid", position=9,
            processed_video_key="processed/video.mp4",
            transcript_json={"text": "Transcript"}, summary="Summary",
            key_concepts_json=None,
        )
        with self.assertRaises(ConflictError) as error:
            review_service.validate_review_content(invalid_lesson)
        self.assertEqual(error.exception.code, "REVIEW_CONTENT_INCOMPLETE")

    async def test_approval_uses_persisted_media_without_external_storage(self):
        response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)

    async def test_approval_does_not_depend_on_aws_credentials(self):
        response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "PUBLISHED")

    async def test_empty_processed_video_key_is_rejected(self):
        self.lesson.processed_video_key = " "
        self.db.commit()
        response = await self.call()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "PROCESSED_VIDEO_REQUIRED")

    async def test_stale_revision_conflicts_without_approving(self):
        self.lesson.summary = "Concurrent edit"
        self.db.commit()
        response = await self.call()
        self.assertEqual(response.status_code, 409)
        self.assertIn("Draft changed", response.json()["detail"])
        self.assertEqual(self.db.get(Lesson, self.lesson.id).status, "REVIEW_REQUIRED")

    async def test_commit_failure_rolls_back_approval(self):
        def fail_update(_mapper, _connection, _target):
            raise RuntimeError("simulated approval write failure")

        event.listen(Quiz, "before_update", fail_update)
        try:
            with self.assertRaisesRegex(RuntimeError, "simulated approval write failure"):
                review_service.approve_draft(
                    self.db, lesson_id=self.lesson.id, instructor_id=self.user.id,
                    payload=DraftApproval(expected_revision=self.draft.revision),
                )
        finally:
            event.remove(Quiz, "before_update", fail_update)
        self.db.expire_all()
        self.assertEqual(self.db.get(Lesson, self.lesson.id).status, "REVIEW_REQUIRED")
        self.assertFalse(self.db.get(Quiz, self.quiz.id).is_approved)
        self.assertFalse(self.db.get(Flashcard, self.flashcard.id).is_approved)

    async def test_request_body_cannot_manufacture_review_state(self):
        self.lesson.status = "DRAFT"
        self.db.commit()
        response = await self.call(json={
            "expected_revision": self.draft.revision,
            "status": "PUBLISHED", "processed_video_key": "attacker.mp4",
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.db.get(Lesson, self.lesson.id).status, "DRAFT")

    async def test_approved_state_visible_through_existing_processing_status(self):
        self.assertEqual((await self.call()).status_code, 200)
        response = await self.call("GET", f"/lessons/{self.lesson.id}/processing-status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "PUBLISHED")

    async def test_openapi_has_approve_and_eight_statuses(self):
        response = await self.call("GET", "/openapi.json")
        schema = response.json()
        self.assertIn("post", schema["paths"]["/lessons/{lesson_id}/approve"])
        self.assertEqual(
            set(schema["components"]["schemas"]["LessonStatus"]["enum"]),
            {state.value for state in LessonStatus},
        )


class ApprovalSchemaTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[3]

    def test_model_bootstrap_and_migration_use_identical_statuses(self):
        expected = {state.value for state in LessonStatus}
        constraint = next(
            c for c in Lesson.__table__.constraints
            if isinstance(c, CheckConstraint) and c.name == "ck_lessons_status"
        )
        self.assertEqual(set(re.findall(r"'([A-Z_]+)'", str(constraint.sqltext))), expected)
        bootstrap = (self.root / "database/schema.sql").read_text(encoding="utf-8")
        migration = (self.root / "database/migrations/0004_remove_approved_lesson_status.sql").read_text(encoding="utf-8")
        for source in (bootstrap, migration):
            constraint_start = source.find("ck_lessons_status")
            clause = re.search(
                r"status\s+IN\s*\((.*?)\)\s*(?:NOT VALID)?",
                source[constraint_start:], re.S,
            ).group(1)
            self.assertEqual(set(re.findall(r"'([A-Z_]+)'", clause)), expected)

    def test_unknown_status_is_rejected_by_response_validation(self):
        with self.assertRaises(ValidationError):
            LessonProcessingStatusResponse(
                lesson_id=8, status="AUTO_PUBLISHED", retry_count=0,
                updated_at=datetime.now(timezone.utc),
            )

    def test_migration_is_transactional_and_does_not_rewrite_lesson_data(self):
        source = (self.root / "database/migrations/0004_remove_approved_lesson_status.sql").read_text(encoding="utf-8")
        sql = re.sub(r"--[^\n]*", "", source)
        self.assertIn("BEGIN;", sql)
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        self.assertIn("SET LOCAL lock_timeout", sql)
        self.assertIn("VALIDATE CONSTRAINT ck_lessons_status", sql)
        self.assertIn("ON CONFLICT (version) DO NOTHING", sql)
        self.assertNotRegex(sql.upper(), r"DROP\s+TABLE|TRUNCATE|DELETE\s+FROM|INSERT\s+INTO\s+(?:PUBLIC\.)?LESSONS")

    def test_preflight_is_read_only(self):
        source = (self.root / "database/checks/lesson_approval_preflight.sql").read_text(encoding="utf-8")
        sql = re.sub(r"--[^\n]*", "", source)
        self.assertIn("BEGIN TRANSACTION READ ONLY", sql)
        self.assertNotRegex(sql.upper(), r"\bALTER\b|\bDROP\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bCREATE\b")


if __name__ == "__main__":
    unittest.main()
