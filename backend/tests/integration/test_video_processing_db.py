"""Opt-in PostgreSQL tests; all fixture mutations are rolled back.

No schema changes, committed fixtures, AWS calls, or background workers.
Set LEARNCLOUD_RUN_DB_TESTS=1 to run against the configured local database.
"""
import os
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, SessionLocal
from app.dependencies import get_db
from app.main import app
from app.repositories import courses_repo, lessons_repo


@unittest.skipUnless(os.environ.get("LEARNCLOUD_RUN_DB_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class ProcessingDatabaseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.connection = self.stack.enter_context(engine.connect())
        self.transaction = self.connection.begin()
        self.addCleanup(self.transaction.rollback)
        fixture = self.connection.execute(text("""
            SELECT l.id AS lesson_id, c.id AS course_id, c.instructor_id
            FROM lessons l JOIN sections s ON s.id=l.section_id
            JOIN courses c ON c.id=s.course_id JOIN users u ON u.id=c.instructor_id
            WHERE c.status='PUBLISHED' AND u.role='INSTRUCTOR'
            ORDER BY l.id LIMIT 1
        """)).mappings().first()
        if fixture is None:
            self.skipTest("No existing published course/instructor/lesson fixture")
        self.lesson_id = fixture["lesson_id"]
        self.course_id = fixture["course_id"]
        self.owner_id = fixture["instructor_id"]
        self.job_dir = Path(self.stack.enter_context(TemporaryDirectory()))
        for name, value in (
            ("APP_ENV", "development"), ("VIDEO_PROCESSOR_BACKEND", "local"),
            ("LOCAL_VIDEO_JOB_DIR", self.job_dir),
        ):
            self.stack.enter_context(patch.object(settings, name, value))
        self.storage = self.stack.enter_context(patch("app.services.processing_service.S3StorageAdapter"))
        self.storage.return_value.head_video.return_value = {"ContentLength": 1024}
        self.review_storage = self.stack.enter_context(patch("app.services.review_service.S3StorageAdapter"))
        self.review_storage.return_value.head_video.return_value = {"ContentLength": 1024}

        def test_db():
            # API commit only releases a savepoint, never commits the outer fixture transaction.
            with Session(bind=self.connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.addCleanup(app.dependency_overrides.clear)

    async def call(self, method, suffix, *, user_id=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, suffix, headers={"X-Demo-User": str(user_id if user_id is not None else self.owner_id)})

    def make_failed(self):
        self.connection.execute(text("""
            UPDATE lessons SET status='FAILED', retry_count=2,
            error_message='SECRET-INTERNAL-ERROR', raw_video_key='tests/input.mp4'
            WHERE id=:id
        """), {"id": self.lesson_id})

    def persisted(self):
        return self.connection.execute(text(
            "SELECT status, retry_count, error_message FROM lessons WHERE id=:id"
        ), {"id": self.lesson_id}).mappings().one()

    async def test_status_reads_actual_postgres_and_redacts_error(self):
        self.make_failed()
        response = await self.call("GET", f"/lessons/{self.lesson_id}/processing-status")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "FAILED")
        self.assertEqual(response.json()["retry_count"], 2)
        self.assertNotIn("SECRET", response.text)

    async def test_retry_transaction_and_duplicate_request(self):
        self.make_failed()
        response = await self.call("POST", f"/lessons/{self.lesson_id}/retry")
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(dict(self.persisted()), {"status": "PROCESSING", "retry_count": 3, "error_message": None})
        self.assertEqual(len(list(self.job_dir.glob("*.json"))), 1)
        duplicate = await self.call("POST", f"/lessons/{self.lesson_id}/retry")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.persisted()["retry_count"], 3)
        self.assertEqual(len(list(self.job_dir.glob("*.json"))), 1)

    async def test_dispatch_failure_rolls_back_real_postgres_update(self):
        self.make_failed()
        self.job_dir = self.job_dir / "occupied"
        self.job_dir.write_text("not a directory", encoding="utf-8")
        with patch.object(settings, "LOCAL_VIDEO_JOB_DIR", self.job_dir):
            response = await self.call("POST", f"/lessons/{self.lesson_id}/retry")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(dict(self.persisted()), {"status": "FAILED", "retry_count": 2, "error_message": "SECRET-INTERNAL-ERROR"})

    async def test_unconfigured_workflow_keeps_real_failure_state(self):
        self.make_failed()
        with patch.object(settings, "VIDEO_PROCESSOR_BACKEND", "disabled"):
            response = await self.call("POST", f"/lessons/{self.lesson_id}/retry")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.persisted()["retry_count"], 2)
        self.storage.assert_not_called()

    async def test_non_failed_real_lesson_cannot_retry(self):
        self.connection.execute(text("UPDATE lessons SET status='PUBLISHED' WHERE id=:id"), {"id": self.lesson_id})
        self.assertEqual((await self.call("POST", f"/lessons/{self.lesson_id}/retry")).status_code, 409)

    async def test_course_lock_blocks_concurrent_retry_and_publish_without_waiting(self):
        with SessionLocal() as holder:
            courses_repo.lock_by_id(holder, self.course_id)
            retry = await self.call("POST", f"/lessons/{self.lesson_id}/retry")
            publish = await self.call("POST", f"/courses/{self.course_id}/publish")
            approve = await self.call("POST", f"/lessons/{self.lesson_id}/approve")
            self.assertEqual(retry.json()["code"], "PROCESSING_BUSY")
            self.assertEqual(publish.json()["code"], "COURSE_BUSY")
            self.assertEqual(retry.status_code, 409)
            self.assertEqual(publish.status_code, 409)
            self.assertEqual(approve.status_code, 409)
            self.assertEqual(approve.json()["code"], "REVIEW_BUSY")

    async def test_lesson_lock_blocks_concurrent_retry_without_dispatch(self):
        with SessionLocal() as holder:
            lessons_repo.lock_by_id(holder, self.lesson_id)
            response = await self.call("POST", f"/lessons/{self.lesson_id}/retry")
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["code"], "PROCESSING_BUSY")
            self.storage.assert_not_called()

    async def test_publish_real_existing_course_is_idempotent(self):
        for _ in range(2):
            response = await self.call("POST", f"/courses/{self.course_id}/publish")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "PUBLISHED")

    async def test_draft_course_with_legacy_published_lessons_has_no_approval_proof(self):
        self.connection.execute(text("UPDATE courses SET status='DRAFT' WHERE id=:id"), {"id": self.course_id})
        response = await self.call("POST", f"/courses/{self.course_id}/publish")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["code"], "LESSON_APPROVAL_REQUIRED")
        self.assertEqual(self.connection.execute(text("SELECT status FROM courses WHERE id=:id"), {"id": self.course_id}).scalar(), "DRAFT")

    def make_review_required(self, lesson_id):
        self.connection.execute(text("""
            UPDATE lessons SET status='REVIEW_REQUIRED', processed_video_key='tests/processed.mp4',
                transcript_json='{"segments":[{"text":"Test fixture transcript"}]}'::jsonb,
                summary='Test fixture summary', key_concepts_json='["Test concept"]'::jsonb
            WHERE id=:id
        """), {"id": lesson_id})

    async def test_approve_then_publish_after_operator_applies_migration(self):
        # Operator applies migration 0004 on a reviewed test DB before this lifecycle check.
        self.connection.execute(text("UPDATE courses SET status='DRAFT' WHERE id=:id"), {"id": self.course_id})
        lesson_ids = list(self.connection.execute(text("""
            SELECT l.id FROM lessons l JOIN sections s ON s.id=l.section_id
            WHERE s.course_id=:course_id ORDER BY l.id
        """), {"course_id": self.course_id}).scalars())
        for lesson_id in lesson_ids:
            self.make_review_required(lesson_id)
            approved = await self.call("POST", f"/lessons/{lesson_id}/approve")
            self.assertEqual(approved.status_code, 200, approved.text)
            self.assertEqual(approved.json()["status"], "PUBLISHED")
            duplicate = await self.call("POST", f"/lessons/{lesson_id}/approve")
            self.assertEqual(duplicate.json(), approved.json())
        published = await self.call("POST", f"/courses/{self.course_id}/publish")
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(published.json()["status"], "PUBLISHED")
        statuses = list(self.connection.execute(text("""
            SELECT l.status FROM lessons l JOIN sections s ON s.id=l.section_id
            WHERE s.course_id=:course_id
        """), {"course_id": self.course_id}).scalars())
        self.assertEqual(set(statuses), {"PUBLISHED"})


if __name__ == "__main__":
    unittest.main()
