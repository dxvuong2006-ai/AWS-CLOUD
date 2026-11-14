import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError, ReadTimeoutError
from botocore.loaders import Loader
from botocore.model import ServiceModel
from botocore.validate import ParamValidator
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.storage.s3_storage import S3StorageAdapter
from app.adapters.video.base import ProcessingReceipt, ProcessorDispatchError, VideoProcessingRequest
from app.adapters.video.mediaconvert import (
    MediaConvertAdapter, MediaConvertConfig, MediaConvertError, build_job_request, output_key, source_identity,
)
from app.config import settings
from app.models.video_pipeline import VideoPipelineRun, VideoUpload
from app.repositories import video_pipeline_repo as repo
from app.services import video_pipeline_service as service
from app.services.upload_service import UploadService

ROOT = Path(__file__).resolve().parents[3]
KEY = "lessons/8/raw/0123456789abcdef0123456789abcdef.mp4"
ETAG = "a" * 32
OWNER = "arn:aws:states:ap-southeast-1:000000000000:execution:unit:one"
OTHER = OWNER + "-duplicate"
BUCKET = "learncloud-videos-mentorcloud"


class MediaConvertTests(unittest.TestCase):
    def setUp(self):
        self.config = MediaConvertConfig(BUCKET, "arn:aws:iam::000000000000:role/unit-mc")
        self.request = VideoProcessingRequest(8, 1, KEY)
        self.client = Mock()
        self.adapter = MediaConvertAdapter(self.config, client=self.client)

    def test_payload_validates_against_installed_aws_service_model_offline(self):
        model = ServiceModel(Loader().load_service_model("mediaconvert", "service-2"))
        payload = self.adapter.build_job_request(self.request)
        errors = ParamValidator().validate(payload, model.operation_model("CreateJob").input_shape)
        self.assertFalse(errors.has_errors(), errors.generate_report())
        output = payload["Settings"]["OutputGroups"][0]["Outputs"][0]
        self.assertEqual(output["VideoDescription"]["Height"], 720)
        self.assertEqual(output["VideoDescription"]["ScalingBehavior"], "FIT_NO_UPSCALE")
        self.assertEqual(output["AudioDescriptions"][0]["CodecSettings"]["Codec"], "AAC")
        self.assertIn("/processed/", payload["Settings"]["OutputGroups"][0]["OutputGroupSettings"]["FileGroupSettings"]["Destination"])
        self.assertNotEqual(KEY, output_key(self.request))
        self.assertIn("FIT_NO_UPSCALE", model.shape_for("ScalingBehavior").enum)
        self.client.create_job.assert_not_called()

    def test_deterministic_token_and_unique_output_per_attempt(self):
        first = build_job_request(self.config, self.request)
        self.assertEqual(first, build_job_request(self.config, self.request))
        next_request = VideoProcessingRequest(8, 2, KEY)
        self.assertNotEqual(first["ClientRequestToken"], build_job_request(self.config, next_request)["ClientRequestToken"])
        self.assertNotEqual(output_key(self.request), output_key(next_request))

    def test_rejects_unissued_key_shapes_and_cross_lesson_input(self):
        for key in ("s3://bucket/key", "../input.mp4", KEY + "?token=secret", KEY.replace("/raw/", "/processed/"), KEY.replace("8/", "9/"), KEY.replace("raw/", "raw/%2e/")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.adapter.build_job_request(VideoProcessingRequest(8, 1, key))
        for bucket in ("", "bucket/path", "https://bucket", "BUCKET", "127.0.0.1"):
            with self.assertRaises(ValueError):
                MediaConvertConfig(bucket, self.config.role_arn)

    def test_real_receipt_requires_job_id(self):
        self.client.create_job.return_value = {"Job": {"Id": "123456789-job"}}
        self.assertEqual(self.adapter.start(self.request).job_id, "123456789-job")
        self.client.create_job.return_value = {"Job": {}}
        with self.assertRaises(MediaConvertError):
            self.adapter.start(self.request)

    def test_retryable_and_permanent_errors_redact_sdk_message(self):
        for code, retryable in (("TooManyRequestsException", True), ("AccessDeniedException", False)):
            self.client.create_job.side_effect = ClientError({"Error": {"Code": code, "Message": "SECRET-PRESIGNED-URL"}}, "CreateJob")
            with self.assertLogs("app.adapters.video.mediaconvert", level="WARNING") as captured:
                with self.assertRaises(MediaConvertError) as caught:
                    self.adapter.start(self.request)
            self.assertEqual(caught.exception.retryable, retryable)
            self.assertNotIn("SECRET", str(caught.exception) + str(captured.output))

    def test_timeout_is_ambiguous_and_does_not_loop(self):
        self.client.create_job.side_effect = ReadTimeoutError(endpoint_url="https://secret.example")
        with self.assertRaises(MediaConvertError) as caught:
            self.adapter.start(self.request)
        self.assertTrue(caught.exception.retryable)
        self.client.create_job.assert_called_once()

    def test_s3_conditional_header_only_added_on_opt_in(self):
        storage = S3StorageAdapter.__new__(S3StorageAdapter)
        storage.bucket, storage.client = BUCKET, Mock()
        storage.generate_upload_url(KEY, "video/mp4", prevent_overwrite=True)
        self.assertEqual(storage.client.generate_presigned_url.call_args.kwargs["Params"]["IfNoneMatch"], "*")
        storage.generate_upload_url(KEY, "video/mp4")
        self.assertNotIn("IfNoneMatch", storage.client.generate_presigned_url.call_args.kwargs["Params"])


class PipelineTests(unittest.TestCase):
    """Real isolated SQLite ledger, fake Lesson repository and injected AWS clients.

    Does not claim to test PostgreSQL locking or any connected development DB.
    """
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            # Only this isolated SQLite fixture: no PostgreSQL/schema migration.
            connection.exec_driver_sql("CREATE TABLE lessons (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO lessons (id) VALUES (8), (9)")
        VideoUpload.__table__.create(self.engine)
        VideoPipelineRun.__table__.create(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.lesson = SimpleNamespace(id=8, section_id=4, status="DRAFT", retry_count=0,
            raw_video_key=None, processed_video_key=None, error_message=None,
            transcript_json=None, summary=None, key_concepts_json=[])
        self.course = SimpleNamespace(id=2, status="DRAFT", instructor_id=1)
        self.section = SimpleNamespace(id=4, course_id=2)
        for name, value in (("lessons_repo.get_by_id", self.lesson), ("lessons_repo.lock_by_id", self.lesson),
                            ("lessons_repo.get_section", self.section), ("courses_repo.lock_by_id", self.course)):
            patcher = patch("app.services.video_pipeline_service." + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        section_lock = patch(
            "app.services.video_pipeline_service.review_repo.lock_section",
            return_value=None,
        )
        section_lock.start()
        self.addCleanup(section_lock.stop)
        now = datetime.now(timezone.utc)
        self.upload = VideoUpload(id=KEY.split("/")[-1][:-4], lesson_id=8, source_key=KEY,
            content_type="video/mp4", size_bytes=1234, created_at=now-timedelta(seconds=10), expires_at=now+timedelta(minutes=15))
        self.db.add(self.upload)
        self.db.commit()
        self.storage = Mock()
        self.storage.head_video.return_value = {"ContentLength": 1234, "ContentType": "video/mp4", "ETag": f'"{ETAG}"', "LastModified": now}
        self.mc = Mock()
        self.mc.start.return_value = ProcessingReceipt("unit-job")
        self.payload = {"kind": "upload", "bucket": BUCKET, "key": KEY, "etag": ETAG}

    def complete_job(self, run, duration_ms=12050):
        destination = f"s3://{BUCKET}/{run.output_key.removesuffix('_720p.mp4')}"
        self.mc.get_job.return_value = {
            "Status": "COMPLETE",
            "Settings": {
                "OutputGroups": [{
                    "OutputGroupSettings": {
                        "FileGroupSettings": {"Destination": destination},
                    },
                    "Outputs": [{"NameModifier": "_720p"}],
                }],
            },
            "OutputGroupDetails": [{
                "OutputDetails": [{"DurationInMs": duration_ms}],
            }],
        }

    def claim(self):
        result = service.claim(self.db, self.payload, OWNER, self.storage)
        return repo.get_run(self.db, result["run_id"])

    def transcode(self):
        run = self.claim()
        service.submit(self.db, run.id, OWNER, self.storage, self.mc)
        return run

    def test_claim_and_duplicate_events_only_one_owner(self):
        run = self.claim()
        self.assertEqual(self.lesson.status, "PROCESSING")
        with self.assertLogs("app.services.video_pipeline_service", level="INFO") as captured:
            self.assertEqual(service.claim(self.db, self.payload, OTHER, self.storage), {"decision": "IGNORE"})
        log_output = " ".join(captured.output)
        self.assertIn("reason=UPLOAD_ALREADY_CLAIMED", log_output)
        self.assertNotIn(KEY, log_output)
        self.assertNotIn(ETAG, log_output)
        self.assertNotIn(OTHER, log_output)
        self.assertEqual(service.claim(self.db, self.payload, OWNER, self.storage)["run_id"], run.id)
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 1)
        self.assertIsNone(self.lesson.processed_video_key)
        self.mc.start.assert_not_called()

    def test_confirmed_uploaded_lesson_with_valid_ledger_and_no_runs_is_claimed(self):
        """Regression: API confirmation may persist UPLOADED before EventBridge claim."""
        self.lesson.status = "UPLOADED"
        self.lesson.raw_video_key = KEY

        run = self.claim()

        self.assertEqual(run.state, "CLAIMED")
        self.assertEqual(run.upload_id, self.upload.id)
        self.assertEqual(run.source_etag, ETAG)
        self.assertEqual(self.lesson.status, "PROCESSING")
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 1)
        self.storage.head_video.assert_called_once_with(KEY)

    def test_uploaded_lesson_requires_exact_current_unprocessed_generation(self):
        self.lesson.status = "UPLOADED"
        for raw_key, processed_key, reason in (
                (None, None, "UPLOADED_GENERATION_MISMATCH"),
                (KEY, "lessons/8/processed/existing.mp4", "UPLOADED_GENERATION_MISMATCH"),
                ("lessons/8/raw/other.mp4", None, "SOURCE_KEY_NOT_CURRENT")):
            with self.subTest(raw_key=raw_key, processed_key=processed_key):
                self.lesson.raw_video_key = raw_key
                self.lesson.processed_video_key = processed_key
                with self.assertLogs("app.services.video_pipeline_service", level="INFO") as captured:
                    result = service.claim(self.db, self.payload, OWNER, self.storage)
                self.assertEqual(result, {"decision": "IGNORE"})
                self.assertIn(f"reason={reason}", " ".join(captured.output))
                self.assertEqual(self.db.query(VideoPipelineRun).count(), 0)
                self.storage.head_video.assert_not_called()

    def test_duplicate_recorded_upload_is_idempotent_after_course_leaves_draft(self):
        run = self.claim()
        self.course.status = "PUBLISHED"
        self.assertEqual(service.claim(self.db, self.payload, OTHER, self.storage), {"decision": "IGNORE"})
        self.assertEqual(service.claim(self.db, self.payload, OWNER, self.storage)["run_id"], run.id)
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 1)
        self.assertEqual(self.storage.head_video.call_count, 1)

    def test_new_upload_still_requires_draft_course(self):
        self.course.status = "PUBLISHED"
        with self.assertRaisesRegex(service.PipelineError, "COURSE_NOT_DRAFT"):
            service.claim(self.db, self.payload, OWNER, self.storage)
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 0)
        self.assertIsNone(self.lesson.raw_video_key)
        self.storage.head_video.assert_not_called()

    def test_unissued_upload_is_rejected_before_non_draft_shortcut(self):
        self.course.status = "PUBLISHED"
        unissued_key = KEY.replace(self.upload.id, "f" * 32)
        with self.assertRaisesRegex(service.PipelineError, "UNISSUED_UPLOAD"):
            service.claim(self.db, {**self.payload, "key": unissued_key}, OTHER, self.storage)
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 0)
        self.storage.head_video.assert_not_called()

    def test_two_upload_intents_for_one_lesson_only_first_validated_claim_wins(self):
        other = VideoUpload(id="f"*32, lesson_id=8, source_key=f"lessons/8/raw/{'f'*32}.mp4",
            content_type="video/mp4", size_bytes=1234,
            created_at=self.upload.created_at, expires_at=self.upload.expires_at)
        self.db.add(other)
        self.db.commit()
        first = self.claim()
        result = service.claim(self.db, {**self.payload, "key": other.source_key}, OTHER, self.storage)
        self.assertEqual(result, {"decision": "IGNORE"})
        self.assertEqual(self.lesson.raw_video_key, KEY)
        self.assertEqual(self.db.query(VideoPipelineRun).one().id, first.id)
        self.assertEqual(self.storage.head_video.call_count, 1)

    def test_stale_issued_upload_is_ignored_after_course_leaves_draft(self):
        other = VideoUpload(id="f"*32, lesson_id=8, source_key=f"lessons/8/raw/{'f'*32}.mp4",
            content_type="video/mp4", size_bytes=1234,
            created_at=self.upload.created_at, expires_at=self.upload.expires_at)
        self.db.add(other)
        self.db.commit()
        self.claim()
        self.course.status = "PUBLISHED"
        result = service.claim(self.db, {**self.payload, "key": other.source_key}, OTHER, self.storage)
        self.assertEqual(result, {"decision": "IGNORE"})
        self.assertEqual(self.lesson.raw_video_key, KEY)
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 1)
        self.assertEqual(self.storage.head_video.call_count, 1)

    def test_composite_fk_rejects_upload_from_another_existing_lesson(self):
        invalid = service._new_run(self.upload, 0, ETAG)
        invalid.lesson_id = 9  # both separate old foreign keys would have accepted this
        self.db.add(invalid)
        with self.assertRaises(IntegrityError):
            self.db.flush()
        self.db.rollback()
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 0)

    def test_repository_matches_both_upload_id_and_lesson_id(self):
        invalid = SimpleNamespace(upload_id=self.upload.id, lesson_id=9)
        self.assertIsNone(repo.upload_for_run(self.db, invalid))
        valid = SimpleNamespace(upload_id=self.upload.id, lesson_id=8)
        self.assertEqual(repo.upload_for_run(self.db, valid).id, self.upload.id)

    def test_wrong_bucket_or_unissued_identity_never_updates_lesson(self):
        for changes in ({"bucket": "other-bucket"}, {"key": KEY.replace("0123", "ffff", 1)},
                        {"key": "lessons/8/processed/a.mp4"}, {"lesson_id": 999}, {"upload_id": "f"*32}):
            with self.assertRaises((service.PipelineError, ValueError)):
                service.claim(self.db, {**self.payload, **changes}, OWNER, self.storage)
        self.assertEqual(self.lesson.status, "DRAFT")
        self.assertEqual(self.db.query(VideoPipelineRun).count(), 0)

    def test_mismatched_metadata_fails_without_submitting(self):
        self.storage.head_video.return_value["ContentLength"] = 0
        with self.assertRaises(service.PipelineError):
            self.claim()
        self.assertEqual(self.lesson.status, "FAILED")
        self.assertEqual(self.db.query(VideoPipelineRun).one().error_code, "UPLOAD_VALIDATION_FAILED")
        self.mc.start.assert_not_called()
        self.assertIsNone(self.lesson.processed_video_key)

    def test_delayed_event_uses_object_write_time(self):
        self.upload.expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
        self.storage.head_video.return_value["LastModified"] = self.upload.expires_at-timedelta(seconds=1)
        self.assertEqual(self.claim().state, "CLAIMED")

    def test_expired_write_and_changed_etag_fail_validation(self):
        self.storage.head_video.return_value["ETag"] = '"' + "b"*32 + '"'
        with self.assertRaises(service.PipelineError):
            self.claim()
        self.assertEqual(self.lesson.status, "FAILED")

    def test_submit_once_and_reinvocation_returns_recorded_job(self):
        run = self.transcode()
        service.submit(self.db, run.id, OWNER, self.storage, self.mc)
        self.mc.start.assert_called_once()
        self.assertEqual(run.job_id, "unit-job")

    def test_unknown_submission_is_fenced_across_retry(self):
        run = self.claim()
        self.mc.start.side_effect = MediaConvertError("MEDIACONVERT_UNAVAILABLE", retryable=True)
        with self.assertRaises(MediaConvertError):
            service.submit(self.db, run.id, OWNER, self.storage, self.mc)
        self.assertEqual(run.state, "SUBMITTING")
        with self.assertRaises(service.PipelineError):
            service.submit(self.db, run.id, OWNER, self.storage, self.mc)
        service.fail(self.db, run.id, OWNER)
        with self.assertRaises(ProcessorDispatchError):
            service.PipelineOutboxProcessor(self.db).start(VideoProcessingRequest(8, 1, KEY))
        self.mc.start.assert_called_once()

    def test_definitive_rejection_can_retry_without_unknown_job(self):
        run = self.claim()
        self.mc.start.side_effect = MediaConvertError("MEDIACONVERT_REJECTED", submission_uncertain=False)
        with self.assertRaises(MediaConvertError):
            service.submit(self.db, run.id, OWNER, self.storage, self.mc)
        service.fail(self.db, run.id, OWNER)
        self.assertTrue(run.safe_to_retry)
        service.PipelineOutboxProcessor(self.db).start(VideoProcessingRequest(8, 1, KEY))
        self.assertEqual(repo.run_for_attempt(self.db, self.upload.id, 1).state, "QUEUED")

    def test_failure_before_submission_is_safe_to_retry(self):
        run = self.claim()
        service.fail(self.db, run.id, OWNER, code="secret-untrusted-error")
        self.assertTrue(run.safe_to_retry)
        self.assertEqual(run.error_code, "PIPELINE_FAILED")

    def test_complete_job_and_existing_output_required_before_save(self):
        run = self.transcode()
        self.mc.get_job.return_value = {"Status": "PROGRESSING"}
        with self.assertRaises(service.PipelineError):
            service.verify_output(self.db, run.id, OWNER, self.storage, self.mc)
        self.assertIsNone(self.lesson.processed_video_key)
        self.mc.get_job.return_value = {"Status": "COMPLETE"}
        self.storage.head_video.side_effect = [self.storage.head_video.return_value, {"ContentLength": 0}]
        with self.assertRaises(service.PipelineError):
            service.verify_output(self.db, run.id, OWNER, self.storage, self.mc)
        self.assertIsNone(self.lesson.processed_video_key)

    def test_missing_duration_metadata_does_not_publish_video_output(self):
        run = self.transcode()
        self.mc.get_job.return_value = {"Status": "COMPLETE", "InputDetails": [{}]}
        with self.assertRaisesRegex(service.PipelineError, "OUTPUT_DURATION_UNAVAILABLE"):
            service.verify_output(self.db, run.id, OWNER, self.storage, self.mc)
        self.assertIsNone(self.lesson.processed_video_key)

    def test_matching_output_duration_is_selected_without_assuming_first_output(self):
        run = self.transcode()
        destination = f"s3://{BUCKET}/{run.output_key.removesuffix('_720p.mp4')}"
        self.mc.get_job.return_value = {
            "Status": "COMPLETE",
            "Settings": {
                "OutputGroups": [{
                    "OutputGroupSettings": {
                        "FileGroupSettings": {"Destination": destination},
                    },
                    "Outputs": [
                        {"NameModifier": "_thumbnail"},
                        {"NameModifier": "_720p"},
                    ],
                }],
            },
            "OutputGroupDetails": [{
                "OutputDetails": [
                    {"DurationInMs": 1},
                    {"DurationInMs": 12050},
                ],
            }],
        }
        service.verify_output(self.db, run.id, OWNER, self.storage, self.mc)
        self.assertEqual(self.lesson.duration_seconds, 13)

    def test_video_ready_keeps_processing_and_ai_fields_empty(self):
        run = self.transcode()
        self.complete_job(run)
        service.verify_output(self.db, run.id, OWNER, self.storage, self.mc)
        self.assertEqual(run.state, "VIDEO_READY")
        self.assertEqual(self.lesson.processed_video_key, run.output_key)
        self.assertEqual(self.lesson.duration_seconds, 13)
        self.assertEqual(self.lesson.status, "PROCESSING")
        for proof in ({"completed": True, "run_id": run.id}, {"completed": False, "run_id": run.id}):
            with self.assertRaises(Exception):
                service.finalize_ai(self.db, run.id, OWNER, proof)
        self.assertEqual(self.lesson.status, "PROCESSING")

    def test_ai_review_requires_current_proof_and_persisted_content(self):
        run = self.transcode()
        self.complete_job(run)
        service.verify_output(self.db, run.id, OWNER, self.storage, self.mc)
        self.lesson.transcript_json = {
            "run_id": run.id,
            "job_id": f"learncloud-k5-{run.id}",
            "source": "aws_transcribe",
            "text": "real worker fixture",
            "segments": [{"text": "real worker fixture"}],
        }
        self.lesson.summary, self.lesson.key_concepts_json = "worker fixture", ["concept"]
        with self.assertRaises(service.PipelineError):
            service.finalize_ai(self.db, run.id, OWNER, {"completed": True, "run_id": "stale"})
        quiz = SimpleNamespace(id=10, is_approved=False)
        with (
            patch.object(service.review_repo, "get_quiz", return_value=quiz),
            patch.object(service.review_repo, "get_questions", return_value=[object()]),
            patch.object(service.review_repo, "get_flashcards", return_value=[object()]),
        ):
            service.finalize_ai(
                self.db, run.id, OWNER,
                {"completed": True, "run_id": run.id},
            )
        self.assertEqual(self.lesson.status, "REVIEW_REQUIRED")
        self.assertEqual(self.course.status, "DRAFT")
        self.assertEqual(service.finalize_ai(self.db, run.id, OWNER, {}), {"status": "REVIEW_REQUIRED"})
        self.lesson.status = "PUBLISHED"
        service.finalize_ai(self.db, run.id, OWNER, {})
        self.assertEqual(self.lesson.status, "PUBLISHED")

    def test_retry_outbox_is_transactional_and_duplicates_are_fenced(self):
        run = self.transcode()
        self.mc.get_job.return_value = {"Status": "ERROR"}
        self.assertEqual(service.poll(self.db, run.id, OWNER, self.mc)["status"], "FAILED")
        service.fail(self.db, run.id, OWNER)
        request = VideoProcessingRequest(8, 1, KEY)
        service.PipelineOutboxProcessor(self.db).start(request)
        self.db.rollback()
        # SQLite reloads timezone=True timestamps without an offset; restore this
        # fixture's UTC semantics after rollback. PostgreSQL TIMESTAMPTZ preserves it.
        self.upload.created_at = self.upload.created_at.replace(tzinfo=timezone.utc)
        self.upload.expires_at = self.upload.expires_at.replace(tzinfo=timezone.utc)
        self.assertIsNone(repo.run_for_attempt(self.db, self.upload.id, 1))
        service.PipelineOutboxProcessor(self.db).start(request)
        self.db.commit()
        self.lesson.status, self.lesson.retry_count = "PROCESSING", 1
        queued = repo.run_for_attempt(self.db, self.upload.id, 1)
        event = {**self.payload, "kind": "retry", "run_id": queued.id}
        service.claim(self.db, event, OTHER, self.storage)
        self.assertEqual(queued.execution_arn, OTHER)
        self.assertEqual(service.claim(self.db, event, OWNER, self.storage), {"decision": "IGNORE"})
        self.assertEqual(service.fail(self.db, run.id, OWNER), {"recorded": False})
        self.assertEqual(self.lesson.status, "PROCESSING")
        service.submit(self.db, queued.id, OTHER, self.storage, self.mc)
        self.complete_job(queued)
        service.verify_output(self.db, queued.id, OTHER, self.storage, self.mc)
        newer_key = self.lesson.processed_video_key
        with self.assertRaises(service.PipelineError):
            service.verify_output(self.db, run.id, OWNER, self.storage, self.mc)
        self.assertEqual(self.lesson.processed_video_key, newer_key)
        self.assertEqual(newer_key, queued.output_key)

    def test_outbox_republishes_until_claim_not_merely_until_putevents(self):
        run = service._new_run(self.upload, 0, ETAG)
        self.db.add(run)
        self.db.commit()
        events = Mock()
        events.put_events.return_value = {"FailedEntryCount": 0}
        self.assertEqual(service.relay_outbox(self.db, events), {"delivered": 1})

    def test_retry_validation_failure_terminates_queued_outbox(self):
        run = self.claim()
        service.fail(self.db, run.id, OWNER)
        service.PipelineOutboxProcessor(self.db).start(VideoProcessingRequest(8, 1, KEY))
        self.db.commit()
        self.lesson.status, self.lesson.retry_count = "PROCESSING", 1
        queued = repo.run_for_attempt(self.db, self.upload.id, 1)
        self.storage.head_video.side_effect = RuntimeError("private-sdk-error")
        with self.assertRaises(service.PipelineError):
            service.claim(self.db, {**self.payload, "kind": "retry", "run_id": queued.id}, OTHER, self.storage)
        self.assertEqual(queued.state, "FAILED")
        self.assertEqual(self.lesson.status, "FAILED")
        self.assertNotIn("private", queued.error_code)

    def test_retry_cannot_bypass_original_upload_expiration_validation(self):
        self.upload.expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
        self.db.commit()
        with self.assertRaises(service.PipelineError):
            self.claim()
        self.assertEqual(self.lesson.status, "FAILED")
        service.PipelineOutboxProcessor(self.db).start(VideoProcessingRequest(8, 1, KEY))
        self.db.commit()
        self.lesson.status, self.lesson.retry_count = "PROCESSING", 1
        queued = repo.run_for_attempt(self.db, self.upload.id, 1)
        with self.assertRaises(service.PipelineError):
            service.claim(self.db, {**self.payload, "kind": "retry", "run_id": queued.id}, OTHER, self.storage)
        self.assertEqual(queued.state, "FAILED")
        self.assertEqual(self.lesson.status, "FAILED")
        self.mc.start.assert_not_called()

    def test_outbox_republish_moves_deadline_without_removing_queued_state(self):
        run = service._new_run(self.upload, 0, ETAG)
        self.db.add(run)
        self.db.commit()
        events = Mock()
        events.put_events.return_value = {"FailedEntryCount": 0}
        service.relay_outbox(self.db, events)
        self.assertEqual(run.state, "QUEUED")
        self.assertEqual(service.relay_outbox(self.db, events), {"delivered": 0})
        run.next_dispatch_at = datetime.now(timezone.utc)-timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(service.relay_outbox(self.db, events), {"delivered": 1})

    def test_database_unique_constraint_rejects_duplicate_run(self):
        run = self.claim()
        duplicate = service._new_run(self.upload, 0, ETAG)
        duplicate.id = "f"*64
        self.db.add(duplicate)
        with self.assertRaises(IntegrityError):
            self.db.flush()

    def test_failed_never_publishes_and_stale_callbacks_cannot_write(self):
        run = self.transcode()
        service.fail(self.db, run.id, OWNER)
        self.assertEqual(self.lesson.status, "FAILED")
        self.assertEqual(self.course.status, "DRAFT")
        with self.assertRaises(service.PipelineError):
            service.verify_output(self.db, run.id, OWNER, self.storage, self.mc)

    def test_reconcile_matches_token_and_requires_terminal_job(self):
        run = self.claim()
        run.state = "SUBMITTING"
        self.db.commit()
        service.fail(self.db, run.id, OWNER)
        self.mc.build_job_request.return_value = {"ClientRequestToken": "expected"}
        self.mc.get_job.return_value = {"Status": "COMPLETE", "UserMetadata": {"token": "wrong"}}
        with self.assertRaises(service.PipelineError):
            service.reconcile(self.db, run.id, "unit-job", self.mc)
        self.mc.get_job.return_value = {"Status": "COMPLETE", "UserMetadata": {"token": "expected"}}
        service.reconcile(self.db, run.id, "unit-job", self.mc)
        self.assertTrue(run.safe_to_retry)

    def test_lambda_verify_rejects_wrong_upload_lesson_pair_without_writing_output(self):
        run = self.transcode()
        spec = importlib.util.spec_from_file_location("video_pipeline_pair_test", ROOT / "infrastructure/lambda/video_pipeline_handler.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.storage.reset_mock()
        self.mc.reset_mock()
        with patch.object(settings, "VIDEO_PIPELINE_ENABLED", True), \
             patch.object(module, "SessionLocal", side_effect=lambda: nullcontext(self.db)), \
             patch.object(module, "S3StorageAdapter", return_value=self.storage), \
             patch.object(module, "_mediaconvert", return_value=self.mc), \
             patch.object(repo, "upload_for_run", return_value=None):
            with self.assertRaises(service.PipelineError) as caught:
                module.handler({"action": "verify", "run_id": run.id, "execution_arn": OWNER}, None)
        self.assertEqual(str(caught.exception), "STALE_EXECUTION")
        self.assertIsNone(self.lesson.processed_video_key)
        self.storage.head_video.assert_not_called()
        self.mc.get_job.assert_not_called()


class UploadCompatibilityTests(unittest.TestCase):
    def reservation(self, enabled, fail=False):
        db, storage = Mock(), Mock()
        storage.has_raw_video_objects.return_value = False
        db.query.return_value.filter_by.return_value.populate_existing.return_value.limit.return_value.all.return_value = []
        storage.generate_upload_url.return_value = "opaque-test-url"
        if fail:
            storage.generate_upload_url.side_effect = RuntimeError("signer unavailable")
        lesson = SimpleNamespace(id=8, status="DRAFT", retry_count=0, raw_video_key=None, processed_video_key=None)
        with patch.object(settings,"VIDEO_PIPELINE_ENABLED",enabled), \
             patch.object(UploadService,"_lock",return_value=(lesson,SimpleNamespace(status="DRAFT"))), \
             patch("app.services.upload_service.ledger_available",return_value=True):
            if fail:
                with self.assertRaises(RuntimeError):
                    UploadService(storage).create_upload_url(db,8,1,"cloud.mp4","video/mp4",100)
                result = None
            else:
                result = UploadService(storage).create_upload_url(db,8,1,"cloud.mp4","video/mp4",100)
        return db, storage, lesson, result

    def test_ledger_and_conditional_put_also_required_when_pipeline_disabled(self):
        db, storage, lesson, result = self.reservation(False)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        self.assertEqual(result["required_headers"]["If-None-Match"],"*")
        self.assertEqual(source_identity(result["object_key"])[1],result["upload_id"])
        self.assertEqual(lesson.status,"DRAFT")
        self.assertIsNone(lesson.raw_video_key)

    def test_opt_in_upload_registers_intent_before_commit_and_returns_required_headers(self):
        db, storage, lesson, result = self.reservation(True)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        self.assertEqual(result["required_headers"]["If-None-Match"], "*")
        self.assertEqual(source_identity(result["object_key"])[1], result["upload_id"])
        self.assertEqual(lesson.status, "DRAFT")

    def test_opt_in_signer_failure_rolls_back_intent(self):
        db, storage, lesson, result = self.reservation(True,fail=True)
        db.commit.assert_not_called()
        db.rollback.assert_called_once()


class InfrastructureTests(unittest.TestCase):
    def test_asl_graph_targets_and_terminal_paths(self):
        asl = json.loads((ROOT / "infrastructure/step-functions/video_pipeline.asl.json").read_text())
        states = asl["States"]
        self.assertIn(asl["StartAt"], states)
        for name, state in states.items():
            targets = [state[k] for k in ("Next", "Default") if k in state]
            targets += [c["Next"] for k in ("Catch", "Choices") for c in state.get(k, [])]
            self.assertTrue(all(t in states for t in targets), name)
            self.assertFalse(state.get("End") and "Next" in state)
        self.assertNotIn("Retry", states["SubmitMediaConvert"])
        claim_choices = {
            choice["StringEquals"]: choice["Next"]
            for choice in states["ClaimDecision"]["Choices"]
        }
        self.assertEqual(claim_choices, {
            "START": "InitPolls",
            "IGNORE": "DuplicateIgnored",
        })
        self.assertEqual(states["ClaimDecision"]["Default"], "InvalidUpload")
        self.assertEqual(states["AIEnabled"]["Default"], "VideoReadyAIPending")
        for state_name in (
            "StartAITranscription", "PollAITranscription", "GenerateAIContent",
        ):
            state = states[state_name]
            self.assertEqual(state["Parameters"]["FunctionName"], "${AI_WORKER_ARN}")
            self.assertIn("AIWorkerTemporaryError", state["Retry"][0]["ErrorEquals"])
        self.assertEqual(
            states["StartAITranscription"]["Parameters"]["Payload"]["action"],
            "start_transcription",
        )
        self.assertEqual(
            states["PollAITranscription"]["Parameters"]["Payload"]["action"],
            "poll_transcription",
        )
        self.assertEqual(
            states["GenerateAIContent"]["Parameters"]["Payload"]["action"],
            "generate_content",
        )
        self.assertGreater(states["GenerateAIContent"]["TimeoutSeconds"], 600)
        self.assertEqual(
            states["ValidateAIAndRequireReview"]["Parameters"]["FunctionName"],
            "${PIPELINE_LAMBDA_ARN}",
        )
        self.assertEqual(states["VideoReadyAIPending"]["Type"], "Succeed")
        self.assertEqual(states["PipelineFailed"]["Type"], "Fail")

    def test_k5_config_is_disabled_and_uses_least_privilege_templates(self):
        env = json.loads((ROOT / "infrastructure/lambda/ai-worker-env.example.json").read_text())
        self.assertEqual(env["Variables"]["AI_WORKER_ENABLED"], "false")
        self.assertEqual(env["Variables"]["VIDEO_AI_ENABLED"], "false")
        self.assertEqual(env["Variables"]["AWS_REGION"], "ap-southeast-1")
        function = json.loads(
            (ROOT / "infrastructure/lambda/ai-worker-function.example.json").read_text()
        )
        self.assertEqual(function["Runtime"], "python3.12")
        self.assertEqual(function["Architectures"], ["x86_64"])
        self.assertEqual(function["Handler"], "ai_worker_handler.handler")
        policy = json.loads(
            (ROOT / "infrastructure/iam/lambda-ai-worker-permissions.json").read_text()
        )
        actions = set()
        for statement in policy["Statement"]:
            value = statement["Action"]
            actions.update(value if isinstance(value, list) else [value])
        self.assertTrue({
            "transcribe:StartTranscriptionJob", "transcribe:GetTranscriptionJob",
            "bedrock:InvokeModel", "s3:GetObject", "s3:PutObject",
            "logs:CreateLogStream", "logs:PutLogEvents",
        }.issubset(actions))
        self.assertFalse(any(action.endswith(":*") for action in actions))
        start = next(
            statement for statement in policy["Statement"]
            if statement["Action"] == "transcribe:StartTranscriptionJob"
        )
        self.assertEqual(start["Resource"], "*")
        self.assertEqual(
            start["Condition"]["StringEquals"]["transcribe:OutputBucketName"],
            "learncloud-videos-mentorcloud",
        )
        self.assertEqual(
            start["Condition"]["StringLike"]["transcribe:OutputKey"],
            "ai-transcripts/*/transcript.json",
        )
        bedrock = [
            statement for statement in policy["Statement"]
            if statement["Action"] == ["bedrock:InvokeModel"]
        ]
        profile_arn = (
            "arn:aws:bedrock:ap-southeast-1:${ACCOUNT_ID}:inference-profile/"
            "apac.amazon.nova-micro-v1:0"
        )
        self.assertEqual(bedrock[0]["Resource"], profile_arn)
        self.assertEqual(
            bedrock[1]["Resource"],
            "arn:aws:bedrock:*::foundation-model/amazon.nova-micro-v1:0",
        )
        self.assertEqual(
            bedrock[1]["Condition"]["StringEquals"]
            ["bedrock:InferenceProfileArn"],
            profile_arn,
        )

    def test_all_json_files_parse_and_raw_filter_excludes_processed(self):
        from fnmatch import fnmatchcase
        for directory in ("infrastructure/iam", "infrastructure/eventbridge", "infrastructure/step-functions", "infrastructure/s3"):
            for path in (ROOT / directory).glob("*.json"):
                json.loads(path.read_text())
        pattern = json.loads((ROOT / "infrastructure/eventbridge/s3-object-created.pattern.json").read_text())
        wildcard = pattern["detail"]["object"]["key"][0]["wildcard"]
        self.assertTrue(fnmatchcase(KEY, wildcard))
        self.assertFalse(fnmatchcase(output_key(VideoProcessingRequest(8, 1, KEY)), wildcard))
        self.assertEqual(pattern["detail"]["bucket"]["name"], [BUCKET])

    def test_lambda_import_and_disabled_handler_do_not_create_clients(self):
        spec = importlib.util.spec_from_file_location("video_pipeline_handler", ROOT / "infrastructure/lambda/video_pipeline_handler.py")
        module = importlib.util.module_from_spec(spec)
        with patch("boto3.client") as client:
            spec.loader.exec_module(module)
            with patch.object(settings, "VIDEO_PIPELINE_ENABLED", False), self.assertRaises(service.PipelineError):
                module.handler({}, None)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
