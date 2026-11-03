"""Opt-in tests against an OPERATOR-PREPARED, isolated local PostgreSQL database.

NOT executed by run_unit_offline.py. No DDL/migrations, no AWS, no committed DML.
Service commits only release savepoints; every test rolls back its outer transaction.
Never uses settings.DATABASE_URL as a fallback. See docs/video-pipeline-migration-0005.md.
"""
import os
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.adapters.video.base import ProcessingReceipt
from app.config import settings
from app.models.video_pipeline import VideoPipelineRun, VideoUpload
from app.repositories import lessons_repo, video_pipeline_repo as repo
from app.services import processing_service, video_pipeline_service as service


def isolated_database_url():
    value = os.environ.get("LEARNCLOUD_PIPELINE_TEST_DATABASE_URL", "")
    try:
        url = make_url(value)
    except Exception:
        raise RuntimeError("An explicit isolated PostgreSQL test URL is required.") from None
    if (url.drivername not in {"postgresql", "postgresql+psycopg2"}
            or url.database != "learncloud_pipeline_test"
            or url.host not in {"localhost", "127.0.0.1", "::1"}
            or not set(url.query).issubset({"sslmode", "connect_timeout", "application_name"})):
        raise RuntimeError("Only local database learncloud_pipeline_test is permitted; development/AWS targets are refused.")
    return url


@unittest.skipUnless(os.environ.get("LEARNCLOUD_RUN_PIPELINE_DB_TESTS") == "1",
                     "Isolated PostgreSQL ledger tests are opt-in; never run on development DB")
class VideoPipelinePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = isolated_database_url()  # guard runs BEFORE constructing/connecting an engine
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.stack.enter_context(patch.dict(os.environ, {
            "AWS_EC2_METADATA_DISABLED": "true", "AWS_ACCESS_KEY_ID": "offline-test-key",
            "AWS_SECRET_ACCESS_KEY": "offline-test-secret", "AWS_SESSION_TOKEN": "offline-test-token",
        }))
        cls.stack.enter_context(patch("boto3.client", side_effect=AssertionError("AWS clients are forbidden in PostgreSQL tests")))
        cls.stack.enter_context(patch("botocore.client.BaseClient._make_api_call",
                                      side_effect=AssertionError("AWS calls are forbidden in PostgreSQL tests")))
        cls.engine = create_engine(url, connect_args={"connect_timeout": 3})
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            if connection.execute(text("SELECT current_database()")).scalar_one() != "learncloud_pipeline_test":
                raise RuntimeError("Unexpected database; refusing fixture mutations.")
            required = connection.execute(text("""
                SELECT version FROM public.schema_migrations WHERE version IN ('0004','0005')
            """)).scalars().all()
            if set(required) != {"0004", "0005"}:
                raise RuntimeError("Operator must review/apply 0004 and reviewed 0005 on the isolated test DB first; tests never run migrations.")
            cls.fixtures = connection.execute(text("""
                SELECT l.id AS lesson_id, c.id AS course_id, c.instructor_id
                FROM public.lessons l JOIN public.sections s ON s.id=l.section_id
                JOIN public.courses c ON c.id=s.course_id JOIN public.users u ON u.id=c.instructor_id
                WHERE c.status='DRAFT' AND l.status='DRAFT' AND u.role='INSTRUCTOR'
                  AND l.retry_count=0 AND l.raw_video_key IS NULL AND l.processed_video_key IS NULL
                  AND NOT EXISTS (SELECT 1 FROM public.video_uploads v WHERE v.lesson_id=l.id)
                ORDER BY l.id LIMIT 2
            """)).mappings().all()
            if len(cls.fixtures) != 2:
                raise RuntimeError("Prepare two pristine DRAFT Lessons in DRAFT Courses using the application on the isolated test DB first.")

    def setUp(self):
        self.connection = self.engine.connect()
        self.addCleanup(self.connection.close)
        self.outer = self.connection.begin()
        self.addCleanup(self.outer.rollback)
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint",
                          expire_on_commit=False, autoflush=False)
        self.addCleanup(self.db.close)
        self.lesson_id = self.fixtures[0]["lesson_id"]
        self.other_lesson_id = self.fixtures[1]["lesson_id"]
        self.owner_id = self.fixtures[0]["instructor_id"]
        self.owner = f"arn:aws:states:ap-southeast-1:000000000000:execution:isolated:{uuid4().hex}"
        self.other_owner = self.owner + "-other"
        now = datetime.now(timezone.utc)
        self.upload = VideoUpload(id=uuid4().hex, lesson_id=self.lesson_id,
            content_type="video/mp4", size_bytes=1234,
            created_at=now-timedelta(seconds=1), expires_at=now+timedelta(minutes=15))
        self.upload.source_key = f"lessons/{self.lesson_id}/raw/{self.upload.id}.mp4"
        self.db.add(self.upload)
        self.db.commit()  # releases a savepoint ONLY; outer transaction stays open
        self.storage, self.mc = Mock(), Mock()
        self.storage.head_video.return_value = {"ContentLength": 1234, "ContentType": "video/mp4",
                                               "ETag": '"' + "a"*32 + '"', "LastModified": now}
        self.mc.start.side_effect = [ProcessingReceipt("fixture-job-one"), ProcessingReceipt("fixture-job-two")]
        self.mc.get_job.return_value = {"Status": "COMPLETE"}
        self.payload = {"kind": "upload", "bucket": settings.S3_BUCKET,
                        "key": self.upload.source_key, "etag": "a"*32}

    def claim(self):
        result = service.claim(self.db, self.payload, self.owner, self.storage)
        return repo.get_run(self.db, result["run_id"])

    def test_0004_and_reviewed_0005_constraints_are_present_and_validated(self):
        rows = self.connection.execute(text("""
            SELECT conname, convalidated, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE conrelid IN (
                'public.lessons'::regclass, 'public.video_uploads'::regclass,
                'public.video_pipeline_runs'::regclass)
        """)).mappings().all()
        constraints = {r["conname"]: r for r in rows}
        for name in ("ck_lessons_status", "uq_video_upload_id_lesson", "fk_video_run_upload_lesson",
                     "uq_video_run_upload_attempt", "ck_video_upload_size", "ck_video_run_attempt", "ck_video_run_state"):
            self.assertTrue(constraints[name]["convalidated"], name)
        self.assertIn("APPROVED", constraints["ck_lessons_status"]["definition"])
        self.assertIn("FOREIGN KEY (upload_id, lesson_id)", constraints["fk_video_run_upload_lesson"]["definition"])

    def test_database_rejects_cross_lesson_upload_reference(self):
        invalid = service._new_run(self.upload, 0, "a"*32)
        invalid.lesson_id = self.other_lesson_id
        with self.assertRaises(IntegrityError) as caught:
            with self.db.begin_nested():
                self.db.add(invalid)
                self.db.flush()
        self.assertEqual(caught.exception.orig.diag.constraint_name, "fk_video_run_upload_lesson")
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 0)

    def test_two_uploads_same_lesson_only_one_can_claim_generation_zero(self):
        other = VideoUpload(id=uuid4().hex, lesson_id=self.lesson_id,
            content_type=self.upload.content_type, size_bytes=self.upload.size_bytes,
            created_at=self.upload.created_at, expires_at=self.upload.expires_at)
        other.source_key = f"lessons/{self.lesson_id}/raw/{other.id}.mp4"
        self.db.add(other)
        self.db.commit()
        run = self.claim()
        result = service.claim(self.db, {**self.payload, "key": other.source_key}, self.other_owner, self.storage)
        self.assertEqual(result, {"decision": "IGNORE"})
        self.assertEqual(self.db.query(VideoPipelineRun).one().id, run.id)
        self.assertEqual(lessons_repo.get_by_id(self.db, self.lesson_id).raw_video_key, self.upload.source_key)

    def test_real_course_lock_rejects_concurrent_claim_before_s3_or_second_run(self):
        self.claim()  # service acquires Course lock; outer transaction retains it
        competing_storage = Mock()
        with Session(self.engine) as competitor:
            with self.assertRaises(OperationalError) as caught:
                service.claim(competitor, self.payload, self.other_owner, competing_storage)
            self.assertEqual(caught.exception.orig.pgcode, "55P03")
            competitor.rollback()
        competing_storage.head_video.assert_not_called()
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 1)

    def test_database_unique_constraint_rejects_same_upload_attempt(self):
        self.claim()
        duplicate = service._new_run(self.upload, 0, "a"*32)
        duplicate.id = "f"*64
        with self.assertRaises(IntegrityError) as caught:
            with self.db.begin_nested():
                self.db.add(duplicate)
                self.db.flush()
        self.assertEqual(caught.exception.orig.diag.constraint_name, "uq_video_run_upload_attempt")

    def test_old_callback_cannot_replace_new_attempt_processed_key(self):
        old = self.claim()
        service.submit(self.db, old.id, self.owner, self.storage, self.mc)
        self.mc.get_job.return_value = {"Status": "ERROR"}
        service.poll(self.db, old.id, self.owner, self.mc)
        service.fail(self.db, old.id, self.owner)
        with patch.object(settings, "VIDEO_PIPELINE_ENABLED", True), \
             patch.object(settings, "VIDEO_PROCESSOR_BACKEND", "eventbridge"), \
             patch.object(processing_service, "_verify_input"):
            processing_service.retry_lesson(self.db, self.lesson_id, user_id=self.owner_id, user_role="INSTRUCTOR")
        newer = repo.run_for_attempt(self.db, self.upload.id, 1)
        service.claim(self.db, {**self.payload, "kind": "retry", "run_id": newer.id}, self.other_owner, self.storage)
        service.submit(self.db, newer.id, self.other_owner, self.storage, self.mc)
        self.mc.get_job.return_value = {"Status": "COMPLETE"}
        service.verify_output(self.db, newer.id, self.other_owner, self.storage, self.mc)
        with self.assertRaisesRegex(service.PipelineError, "STALE_EXECUTION"):
            service.verify_output(self.db, old.id, self.owner, self.storage, self.mc)
        self.assertFalse(service.fail(self.db, old.id, self.owner)["recorded"])
        lesson = lessons_repo.get_by_id(self.db, self.lesson_id)
        self.db.refresh(lesson)
        self.assertEqual(lesson.processed_video_key, newer.output_key)
        self.assertNotEqual(lesson.processed_video_key, old.output_key)
        self.assertEqual(lesson.status, "PROCESSING")


if __name__ == "__main__":
    unittest.main()
