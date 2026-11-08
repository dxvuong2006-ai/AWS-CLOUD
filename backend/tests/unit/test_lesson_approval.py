import re
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from botocore.exceptions import ClientError, NoCredentialsError
from pydantic import ValidationError
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import OperationalError

from app.dependencies import get_db
from app.lesson_states import LessonStatus
from app.main import app
from app.models.lesson import Lesson
from app.schemas.lesson import LessonProcessingStatusResponse
from app.services import review_service


class ApprovalApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.user = SimpleNamespace(id=1, role="INSTRUCTOR")
        self.db = Mock()
        self.db.query.return_value.filter.return_value.first.return_value = self.user
        app.dependency_overrides[get_db] = lambda: self.db
        self.addCleanup(app.dependency_overrides.clear)
        now = datetime.now(timezone.utc)
        self.lesson = SimpleNamespace(
            id=8, section_id=4, status="REVIEW_REQUIRED", raw_video_key="raw/original.mp4",
            processed_video_key="processed/reviewed.mp4", transcript_json={"segments": [{"text": "Reviewed transcript"}]},
            summary="Reviewed summary", key_concepts_json=["Containers"], error_message=None,
            retry_count=2, updated_at=now,
        )
        self.course = SimpleNamespace(
            id=2, instructor_id=1, status="DRAFT", title="Approval test", description=None,
            learning_objectives=[], created_at=now, updated_at=now,
        )
        self.section = SimpleNamespace(id=4, course_id=2)
        self.repo = {}
        for module, name, result in [
            ("lessons_repo", "get_by_id", self.lesson), ("lessons_repo", "get_section", self.section),
            ("lessons_repo", "get_course", self.course), ("lessons_repo", "lock_by_id", self.lesson),
            ("lessons_repo", "lock_by_course", [self.lesson]),
            ("courses_repo", "lock_by_id", self.course), ("courses_repo", "lock_sections", [self.section]),
        ]:
            self.repo[f"{module}.{name}"] = self.stack.enter_context(patch(
                f"app.repositories.{module}.{name}", return_value=result
            ))
        self.storage = self.stack.enter_context(patch("app.services.review_service.S3StorageAdapter"))
        self.storage.return_value.head_video.return_value = {"ContentLength": 1024}
        lesson_snapshot, course_snapshot = dict(vars(self.lesson)), dict(vars(self.course))
        self.db.commit.side_effect = lambda: (lesson_snapshot.update(vars(self.lesson)), course_snapshot.update(vars(self.course)))
        self.db.rollback.side_effect = lambda: (vars(self.lesson).update(lesson_snapshot), vars(self.course).update(course_snapshot))

    async def call(self, method="POST", path="/lessons/8/approve", **kwargs):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    async def test_explicit_approval_is_separate_from_publish_and_idempotent(self):
        response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["lesson_id"], 8)
        self.assertEqual(response.json()["status"], "PUBLISHED")
        self.assertIn("revision", response.json())
        self.assertEqual(self.course.status, "DRAFT")
        self.assertEqual(self.lesson.retry_count, 2)
        self.assertEqual(self.lesson.summary, "Reviewed summary")
        self.storage.return_value.head_video.assert_called_once_with("processed/reviewed.mp4")
        duplicate = await self.call()
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(response.json(), duplicate.json())
        self.storage.return_value.head_video.assert_called_once()

    async def test_review_approve_publish_workflow(self):
        response = await self.call(path="/courses/2/publish")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "LESSON_APPROVAL_REQUIRED")
        self.assertEqual((await self.call()).status_code, 200)
        published = await self.call(path="/courses/2/publish")
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual((self.course.status, self.lesson.status), ("PUBLISHED", "PUBLISHED"))
        self.assertEqual((await self.call(path="/courses/2/publish")).status_code, 200)

    async def test_publish_rejects_content_that_became_incomplete_after_approval(self):
        await self.call()
        self.lesson.summary = ""
        response = await self.call(path="/courses/2/publish")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "REVIEW_CONTENT_INCOMPLETE")
        self.assertEqual(self.course.status, "DRAFT")

    async def test_missing_lesson(self):
        self.repo["lessons_repo.get_by_id"].return_value = None
        self.assertEqual((await self.call()).status_code, 404)

    async def test_owner_required_before_approval_or_idempotency(self):
        self.course.instructor_id = 99
        self.lesson.status = "PUBLISHED"
        self.assertEqual((await self.call()).status_code, 403)
        self.storage.assert_not_called()

    async def test_student_and_admin_cannot_approve(self):
        for role in ("STUDENT", "ADMIN"):
            self.user.role = role
            self.assertEqual((await self.call()).status_code, 403)
        self.storage.assert_not_called()

    async def test_unknown_identity(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        self.assertEqual((await self.call()).status_code, 401)

    async def test_ownership_is_rechecked_under_lock(self):
        def transfer(_db, _course_id):
            self.course.instructor_id = 99
            return self.course
        self.repo["courses_repo.lock_by_id"].side_effect = transfer
        self.assertEqual((await self.call()).status_code, 403)
        self.storage.assert_not_called()

    async def test_every_non_reviewable_state_is_rejected(self):
        for state in ("DRAFT", "UPLOADED", "PROCESSING", "TRANSCRIBING", "AI_PROCESSING", "FAILED"):
            self.lesson.status = state
            response = await self.call()
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["code"], "LESSON_NOT_REVIEWABLE")
        self.storage.assert_not_called()

    async def test_published_course_cannot_receive_new_approval(self):
        self.course.status = "PUBLISHED"
        self.assertEqual((await self.call()).json()["code"], "COURSE_NOT_DRAFT")

    async def test_raw_upload_does_not_substitute_for_processed_video(self):
        self.lesson.processed_video_key = None
        self.assertEqual((await self.call()).json()["code"], "PROCESSED_VIDEO_REQUIRED")
        self.db.flush.assert_not_called()

    async def test_empty_review_content_is_rejected(self):
        for field, value in (("transcript_json", None), ("transcript_json", {}), ("transcript_json", []),
                             ("summary", " "), ("summary", None), ("key_concepts_json", []), ("key_concepts_json", None)):
            setattr(self.lesson, field, value)
            response = await self.call()
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["code"], "REVIEW_CONTENT_INCOMPLETE")
        self.storage.assert_not_called()

    async def test_s3_errors_do_not_approve_or_leak_internal_messages(self):
        for code, http_status, expected in (("NoSuchKey", 404, 409), ("NoSuchBucket", 404, 502), ("AccessDenied", 403, 502)):
            self.storage.return_value.head_video.side_effect = ClientError({
                "Error": {"Code": code, "Message": "SECRET-SIGNED-URL"},
                "ResponseMetadata": {"HTTPStatusCode": http_status},
            }, "HeadObject")
            response = await self.call()
            self.assertEqual(response.status_code, expected)
            self.assertNotIn("SECRET", response.text)
            self.assertEqual(self.lesson.status, "REVIEW_REQUIRED")
        self.db.flush.assert_not_called()

    async def test_missing_credentials(self):
        self.storage.side_effect = NoCredentialsError()
        response = await self.call()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "APPROVAL_STORAGE_UNAVAILABLE")

    async def test_empty_processed_object(self):
        self.storage.return_value.head_video.return_value = {"ContentLength": 0}
        self.assertEqual((await self.call()).json()["code"], "INVALID_PROCESSED_VIDEO")

    async def test_concurrent_review_retry_or_publish_conflicts(self):
        error = Exception("locked")
        error.pgcode = "55P03"
        self.repo["courses_repo.lock_by_id"].side_effect = OperationalError("SELECT", {}, error)
        response = await self.call()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "REVIEW_BUSY")

    async def test_commit_failure_rolls_back_approval(self):
        self.db.commit.side_effect = RuntimeError("commit failed")
        with self.assertRaises(RuntimeError):
            review_service.approve_lesson(self.db, 8, instructor_id=1)
        self.assertEqual(self.lesson.status, "REVIEW_REQUIRED")
        self.assertEqual(self.course.status, "DRAFT")

    async def test_request_body_cannot_manufacture_review_state(self):
        self.lesson.status = "DRAFT"
        response = await self.call(json={"status": "PUBLISHED", "processed_video_key": "attacker.mp4"})
        self.assertEqual(response.status_code, 409)
        self.storage.assert_not_called()

    async def test_approved_state_visible_through_existing_processing_status(self):
        await self.call()
        response = await self.call("GET", "/lessons/8/processing-status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "PUBLISHED")

    async def test_openapi_has_approve_and_eight_statuses(self):
        response = await self.call("GET", "/openapi.json")
        schema = response.json()
        self.assertIn("post", schema["paths"]["/lessons/{lesson_id}/approve"])
        self.assertEqual(set(schema["components"]["schemas"]["LessonStatus"]["enum"]), {s.value for s in LessonStatus})


class ApprovalSchemaTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[3]

    def test_model_bootstrap_and_migration_use_identical_statuses(self):
        expected = {state.value for state in LessonStatus}
        constraint = next(c for c in Lesson.__table__.constraints if isinstance(c, CheckConstraint) and c.name == "ck_lessons_status")
        self.assertEqual(set(re.findall(r"'([A-Z_]+)'", str(constraint.sqltext))), expected)
        bootstrap = (self.root / "database/schema.sql").read_text(encoding="utf-8")
        migration = (self.root / "database/migrations/0004_remove_approved_lesson_status.sql").read_text(encoding="utf-8")
        for source in (bootstrap, migration):
            constraint_start = source.find("ck_lessons_status")
            clause_source = source[constraint_start:]
            clause = re.search(r"status\s+IN\s*\((.*?)\)\s*(?:NOT VALID)?", clause_source, re.S).group(1)
            self.assertEqual(set(re.findall(r"'([A-Z_]+)'", clause)), expected)

    def test_unknown_status_is_rejected_by_response_validation(self):
        with self.assertRaises(ValidationError):
            LessonProcessingStatusResponse(lesson_id=8, status="AUTO_PUBLISHED", retry_count=0, updated_at=datetime.now(timezone.utc))

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
