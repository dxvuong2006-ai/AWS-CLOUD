import json
import logging
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from botocore.exceptions import ClientError, NoCredentialsError
from sqlalchemy.exc import OperationalError

from app.adapters.video.base import ProcessingReceipt, ProcessorDispatchError, VideoProcessingRequest
from app.adapters.video.local_processor import LocalProcessor
from app.config import settings
from app.dependencies import get_db
from app.main import app
from app.services import processing_service


class ProcessingApiTests(unittest.IsolatedAsyncioTestCase):
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
            id=8, section_id=4, status="FAILED", raw_video_key="lessons/8/raw/source.mp4",
            processed_video_key=None, retry_count=2, error_message="SECRET-AWS-URL",
            transcript_json={"segments": [{"text": "Unit fixture"}]},
            summary="Unit fixture summary", key_concepts_json=["Unit fixture concept"],
            updated_at=now,
        )
        self.course = SimpleNamespace(
            id=2, instructor_id=1, status="DRAFT", title="Test course", description=None,
            learning_objectives=[], created_at=now, updated_at=now,
        )
        self.section = SimpleNamespace(id=4, course_id=2)
        self.repo = {}
        for module, name, result in [
            ("lessons_repo", "get_by_id", self.lesson),
            ("lessons_repo", "get_section", self.section),
            ("lessons_repo", "get_course", self.course),
            ("lessons_repo", "lock_by_id", self.lesson),
            ("lessons_repo", "lock_by_course", [self.lesson]),
            ("courses_repo", "lock_by_id", self.course),
            ("courses_repo", "lock_sections", [self.section]),
        ]:
            self.repo[f"{module}.{name}"] = self.stack.enter_context(patch(
                f"app.repositories.{module}.{name}", return_value=result
            ))
        self.storage = self.stack.enter_context(patch("app.services.processing_service.S3StorageAdapter"))
        self.storage.return_value.head_video.return_value = {"ContentLength": 1024, "ContentType": "video/mp4"}
        self.processor = Mock()
        self.processor.start.side_effect = lambda request: ProcessingReceipt(request.job_id)
        self.factory = self.stack.enter_context(patch(
            "app.services.processing_service.get_video_processor", return_value=self.processor
        ))
        snapshot = dict(vars(self.lesson))
        self.db.rollback.side_effect = lambda: vars(self.lesson).update(snapshot)
        self.db.commit.side_effect = lambda: snapshot.update(vars(self.lesson))

    async def call(self, method, path):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path)

    async def retry(self):
        return await self.call("POST", "/lessons/8/retry")

    async def publish(self):
        return await self.call("POST", "/courses/2/publish")

    async def test_status_is_real_and_redacts_internal_error_and_keys(self):
        response = await self.call("GET", "/lessons/8/processing-status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "FAILED")
        self.assertEqual(response.json()["retry_count"], 2)
        self.assertIn("failed", response.json()["error_message"])
        self.assertNotIn("SECRET", response.text)
        self.assertNotIn(self.lesson.raw_video_key, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.storage.assert_not_called()

    async def test_all_contract_statuses_are_returned_without_fake_advancement(self):
        for state in ("DRAFT", "UPLOADED", "PROCESSING", "TRANSCRIBING", "AI_PROCESSING", "REVIEW_REQUIRED", "PUBLISHED", "FAILED"):
            self.lesson.status = state
            response = await self.call("GET", "/lessons/8/processing-status")
            self.assertEqual(response.json()["status"], state)
            if state != "FAILED":
                self.assertIsNone(response.json()["error_message"])

    async def test_status_denies_student_and_admin(self):
        for role in ("STUDENT", "ADMIN"):
            self.user.role = role
            self.assertEqual((await self.call("GET", "/lessons/8/processing-status")).status_code, 403)

    async def test_status_missing_lesson(self):
        self.repo["lessons_repo.get_by_id"].return_value = None
        self.assertEqual((await self.call("GET", "/lessons/8/processing-status")).status_code, 404)

    async def test_owner_required_for_status_and_retry(self):
        self.course.instructor_id = 999
        self.assertEqual((await self.call("GET", "/lessons/8/processing-status")).status_code, 403)
        self.assertEqual((await self.retry()).status_code, 403)
        self.processor.start.assert_not_called()

    async def test_retry_accepts_only_once_and_clears_error_after_verified_input(self):
        response = await self.retry()
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["status"], "PROCESSING")
        self.assertEqual(response.json()["retry_count"], 3)
        self.assertIsNone(self.lesson.error_message)
        self.storage.return_value.head_video.assert_called_once_with(self.lesson.raw_video_key)
        job = self.processor.start.call_args.args[0]
        self.assertEqual(job.job_id, "lesson-8-retry-3")
        self.assertEqual((await self.retry()).status_code, 409)
        self.assertEqual(self.lesson.retry_count, 3)
        self.processor.start.assert_called_once()
        self.db.commit.assert_called_once()

    async def test_retry_admin_allowed_by_contract(self):
        self.user.role = "ADMIN"
        self.course.instructor_id = 999
        self.assertEqual((await self.retry()).status_code, 202)

    async def test_retry_student_denied(self):
        self.user.role = "STUDENT"
        self.assertEqual((await self.retry()).status_code, 403)
        self.factory.assert_not_called()

    async def test_retry_missing_lesson(self):
        self.repo["lessons_repo.get_by_id"].return_value = None
        self.assertEqual((await self.retry()).status_code, 404)

    async def test_retry_rejects_every_non_failed_state(self):
        for state in ("DRAFT", "UPLOADED", "PROCESSING", "TRANSCRIBING", "AI_PROCESSING", "REVIEW_REQUIRED", "PUBLISHED"):
            self.lesson.status = state
            response = await self.retry()
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["code"], "LESSON_NOT_FAILED")
        self.storage.assert_not_called()

    async def test_retry_requires_raw_video(self):
        self.lesson.raw_video_key = None
        self.assertEqual((await self.retry()).json()["code"], "RAW_VIDEO_REQUIRED")
        self.processor.start.assert_not_called()

    async def test_disabled_workflow_does_not_mutate_failed_lesson(self):
        self.factory.side_effect = processing_service.WorkflowUnavailableError()
        response = await self.retry()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.lesson.status, "FAILED")
        self.assertEqual(self.lesson.retry_count, 2)
        self.assertEqual(self.lesson.error_message, "SECRET-AWS-URL")
        self.db.commit.assert_not_called()

    async def test_invalid_or_unreadable_input_never_starts_job(self):
        for code, http_status, expected in (("NoSuchKey", 404, 404), ("AccessDenied", 403, 502), ("NoSuchBucket", 404, 502)):
            self.storage.return_value.head_video.side_effect = ClientError(
                {"Error": {"Code": code, "Message": "SECRET"}, "ResponseMetadata": {"HTTPStatusCode": http_status}}, "HeadObject"
            )
            response = await self.retry()
            self.assertEqual(response.status_code, expected)
            self.assertNotIn("SECRET", response.text)
        self.processor.start.assert_not_called()
        self.db.commit.assert_not_called()

    async def test_missing_credentials_is_storage_error(self):
        self.storage.side_effect = NoCredentialsError()
        self.assertEqual((await self.retry()).status_code, 502)
        self.assertEqual(self.lesson.retry_count, 2)

    async def test_empty_object_is_rejected(self):
        self.storage.return_value.head_video.return_value = {"ContentLength": 0}
        self.assertEqual((await self.retry()).status_code, 409)
        self.processor.start.assert_not_called()

    async def test_dispatch_failure_rolls_back_count_status_and_error(self):
        self.processor.start.side_effect = ProcessorDispatchError("SECRET path")
        response = await self.retry()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.lesson.status, "FAILED")
        self.assertEqual(self.lesson.retry_count, 2)
        self.assertEqual(self.lesson.error_message, "SECRET-AWS-URL")
        self.assertNotIn("SECRET", response.text)
        self.db.commit.assert_not_called()

    async def test_retry_after_commit_failure_reuses_one_local_manifest(self):
        with TemporaryDirectory() as directory:
            self.factory.return_value = LocalProcessor(Path(directory))
            self.db.commit.side_effect = RuntimeError("database unavailable")
            with self.assertRaises(RuntimeError):
                processing_service.retry_lesson(self.db, 8, user_id=1, user_role="INSTRUCTOR")
            self.assertEqual(self.lesson.status, "FAILED")
            self.assertEqual(self.lesson.retry_count, 2)
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)
            self.db.commit.side_effect = None
            result = processing_service.retry_lesson(self.db, 8, user_id=1, user_role="INSTRUCTOR")
            self.assertEqual(result["retry_count"], 3)
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)

    async def test_busy_retry_returns_conflict(self):
        error = Exception("locked")
        error.pgcode = "55P03"
        self.repo["lessons_repo.lock_by_id"].side_effect = OperationalError("SELECT", {}, error)
        self.assertEqual((await self.retry()).json()["code"], "PROCESSING_BUSY")
        self.processor.start.assert_not_called()

    async def test_publish_unapproved_content_is_rejected(self):
        for state in ("DRAFT", "UPLOADED", "PROCESSING", "FAILED", "REVIEW_REQUIRED", "PUBLISHED"):
            self.lesson.status = state
            response = await self.publish()
            self.assertEqual(response.status_code, 409)
            expected = "PROCESSED_VIDEO_REQUIRED" if state == "PUBLISHED" else "LESSON_APPROVAL_REQUIRED"
            self.assertEqual(response.json()["code"], expected)
        self.assertEqual(self.course.status, "DRAFT")
        self.db.commit.assert_not_called()

    async def test_publish_empty_course_or_section_is_rejected(self):
        self.repo["lessons_repo.lock_by_course"].return_value = []
        self.assertEqual((await self.publish()).json()["code"], "COURSE_CONTENT_REQUIRED")

    async def test_publish_requires_processed_video_even_when_approved(self):
        self.lesson.status = "PUBLISHED"
        self.assertEqual((await self.publish()).json()["code"], "PROCESSED_VIDEO_REQUIRED")

    async def test_publish_approved_fixture_and_idempotent_duplicate(self):
        # Unit fixture; existing PostgreSQL needs manually applied migration 0004.
        self.lesson.status = "PUBLISHED"
        self.lesson.processed_video_key = "processed/video.mp4"
        first = await self.publish()
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.lesson.status, "PUBLISHED")
        second = await self.publish()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "PUBLISHED")
        self.repo["lessons_repo.lock_by_course"].assert_called_once()

    async def test_publish_wrong_instructor_or_role_is_denied(self):
        self.course.instructor_id = 999
        self.assertEqual((await self.publish()).status_code, 403)
        self.user.role = "ADMIN"
        self.assertEqual((await self.publish()).status_code, 403)

    async def test_publish_missing_course(self):
        self.repo["courses_repo.lock_by_id"].return_value = None
        self.assertEqual((await self.publish()).status_code, 404)

    async def test_publish_invalid_course_state(self):
        self.course.status = "ARCHIVED"
        self.assertEqual((await self.publish()).json()["code"], "INVALID_COURSE_STATUS")

    async def test_publish_concurrent_request_conflicts(self):
        error = Exception("locked")
        error.pgcode = "55P03"
        self.repo["courses_repo.lock_by_id"].side_effect = OperationalError("SELECT", {}, error)
        self.assertEqual((await self.publish()).json()["code"], "COURSE_BUSY")

    async def test_unknown_identity_rejected_for_all_new_endpoints(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        for method, path in (("GET", "/lessons/8/processing-status"), ("POST", "/lessons/8/retry"), ("POST", "/courses/2/publish")):
            self.assertEqual((await self.call(method, path)).status_code, 401)

    async def test_openapi_registers_status_retry_publish_once(self):
        response = await self.call("GET", "/openapi.json")
        paths = response.json()["paths"]
        self.assertIn("get", paths["/lessons/{lesson_id}/processing-status"])
        self.assertIn("202", paths["/lessons/{lesson_id}/retry"]["post"]["responses"])
        self.assertIn("post", paths["/courses/{course_id}/publish"])


class LocalProcessorTests(unittest.TestCase):
    def test_local_queue_is_durable_and_duplicate_concurrent_dispatch_is_idempotent(self):
        with TemporaryDirectory() as root:
            processor = LocalProcessor(Path(root))
            request = VideoProcessingRequest(8, 1, "lessons/8/raw/source.mp4")
            with ThreadPoolExecutor(max_workers=4) as pool:
                receipts = list(pool.map(lambda _: processor.start(request), range(8)))
            self.assertEqual({r.job_id for r in receipts}, {request.job_id})
            files = list(Path(root).iterdir())
            self.assertEqual(len(files), 1)
            payload = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["kind"], "local_pending_request")
            self.assertNotIn("summary", payload)
            self.assertNotIn("processed_video_key", payload)

    def test_local_job_id_cannot_be_reused_for_another_source(self):
        with TemporaryDirectory() as root:
            processor = LocalProcessor(Path(root))
            processor.start(VideoProcessingRequest(8, 1, "first.mp4"))
            with self.assertRaises(ProcessorDispatchError):
                processor.start(VideoProcessingRequest(8, 1, "second.mp4"))

    def test_local_filesystem_failure_is_controlled(self):
        with TemporaryDirectory() as root:
            destination = Path(root) / "not-a-directory"
            destination.write_text("occupied", encoding="utf-8")
            with self.assertRaises(ProcessorDispatchError):
                LocalProcessor(destination).start(VideoProcessingRequest(8, 1, "source.mp4"))

    def test_local_never_activates_in_production(self):
        with patch.object(settings, "APP_ENV", "production"), patch.object(settings, "VIDEO_PROCESSOR_BACKEND", "local"):
            with self.assertRaises(processing_service.WorkflowUnavailableError):
                processing_service.get_video_processor()

    def test_local_requires_explicit_development_opt_in(self):
        with patch.object(settings, "APP_ENV", "development"), patch.object(settings, "VIDEO_PROCESSOR_BACKEND", "disabled"):
            with self.assertRaises(processing_service.WorkflowUnavailableError):
                processing_service.get_video_processor()


if __name__ == "__main__":
    unittest.main()
