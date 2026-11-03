"""Internal pipeline service. Never invoked automatically at import/startup.

All claims use PostgreSQL row locks and a durable ledger. No DB schema creation.
S3 EventBridge is the sole initial-upload dispatcher; confirmation is the verified
S3 write itself, not an unimplemented confirm-upload endpoint.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import re

from app.adapters.video.base import ProcessingReceipt, ProcessorDispatchError, VideoProcessingRequest
from app.adapters.video.mediaconvert import MediaConvertError, output_key, source_identity
from app.config import settings
from app.models.video_pipeline import VideoPipelineRun, VideoUpload
from app.repositories import courses_repo, lessons_repo, video_pipeline_repo as repo
from app.services.review_service import validate_review_content

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Only constant, safe codes cross the Lambda boundary."""


class PipelineTemporaryError(PipelineError):
    pass


def _now():
    return datetime.now(timezone.utc)


def run_identity(upload_id: str, attempt: int) -> str:
    return hashlib.sha256(f"{upload_id}:{attempt}".encode()).hexdigest()


def register_upload(db, *, upload_id, lesson_id, key, content_type, size_bytes):
    """Caller has locked course/lesson; save intent BEFORE returning the URL."""
    source_identity(key, lesson_id)
    db.add(VideoUpload(id=upload_id, lesson_id=lesson_id, source_key=key,
                       content_type=content_type, size_bytes=size_bytes,
                       expires_at=_now() + timedelta(seconds=900)))
    db.flush()


def _lock_lesson(db, lesson_id):
    lesson = lessons_repo.get_by_id(db, lesson_id)
    if lesson is None:
        raise PipelineError("LESSON_NOT_FOUND")
    section = lessons_repo.get_section(db, lesson.section_id)
    if section is None:
        raise PipelineError("SECTION_NOT_FOUND")
    course = courses_repo.lock_by_id(db, section.course_id)
    lesson = lessons_repo.lock_by_id(db, lesson_id)
    if course is None or lesson is None or course.status != "DRAFT":
        raise PipelineError("COURSE_NOT_DRAFT")
    return lesson


def _etag(value):
    if not isinstance(value, str) or not re.fullmatch(r'"?[A-Fa-f0-9-]{1,126}"?', value):
        raise PipelineError("INVALID_OBJECT_ETAG")
    return value.strip('"').lower()


def _head_source(storage, upload, *, etag=None, initial=False):
    metadata = storage.head_video(upload.source_key)
    actual_etag = _etag(metadata.get("ETag"))
    if (metadata.get("ContentLength") != upload.size_bytes
            or metadata.get("ContentType") != upload.content_type
            or (etag is not None and actual_etag != _etag(etag))):
        raise PipelineError("UPLOAD_METADATA_MISMATCH")
    if initial:
        # Check S3 write time, not delivery time: valid events can arrive late.
        modified = metadata.get("LastModified")
        if not isinstance(modified, datetime) or modified.tzinfo is None:
            raise PipelineError("INVALID_UPLOAD_TIME")
        if not upload.created_at.replace(microsecond=0) <= modified <= upload.expires_at:
            raise PipelineError("UPLOAD_EXPIRED")
    return actual_etag


def _new_run(upload, attempt, etag, *, state="QUEUED", execution_arn=None):
    request = VideoProcessingRequest(upload.lesson_id, attempt + 1, upload.source_key)
    return VideoPipelineRun(id=run_identity(upload.id, attempt), upload_id=upload.id,
                            lesson_id=upload.lesson_id, attempt=attempt, state=state,
                            execution_arn=execution_arn, source_etag=etag,
                            output_key=output_key(request), safe_to_retry=True)


def _view(run):
    return {"decision": "START", "run_id": run.id, "ai_enabled": settings.VIDEO_AI_ENABLED}


def _clear_previous_content(lesson):
    # New generation must never inherit AI approval evidence from an older run.
    lesson.processed_video_key = None
    lesson.transcript_json = None
    lesson.summary = None
    lesson.key_concepts_json = []


def claim(db, payload, execution_arn, storage):
    if not isinstance(payload, dict) or payload.get("bucket") != settings.S3_BUCKET:
        raise PipelineError("INVALID_EVENT_BUCKET")
    key = payload.get("key")
    lesson_id, upload_id = source_identity(key)
    if (("lesson_id" in payload and payload["lesson_id"] != lesson_id)
            or ("upload_id" in payload and payload["upload_id"] != upload_id)):
        raise PipelineError("EVENT_IDENTITY_MISMATCH")
    if payload.get("kind") not in {"upload", "retry"}:
        raise PipelineError("INVALID_EVENT_KIND")
    lesson = _lock_lesson(db, lesson_id)
    upload = repo.get_upload(db, key)
    if upload is None or upload.id != upload_id or upload.lesson_id != lesson_id:
        raise PipelineError("UNISSUED_UPLOAD")
    if payload["kind"] == "upload":
        run = repo.run_for_attempt(db, upload.id, 0)
        if run is not None:
            return _view(run) if run.execution_arn == execution_arn else {"decision": "IGNORE"}
        if lesson.status != "DRAFT" or lesson.retry_count != 0:
            return {"decision": "IGNORE"}
        etag = _etag(payload.get("etag"))
        try:
            etag = _head_source(storage, upload, etag=etag, initial=True)
        except Exception:
            # This is an issued upload owned by a draft Lesson. Record the failed
            # validation without processing it, and without copying SDK errors.
            run = _new_run(upload, 0, etag, state="FAILED", execution_arn=execution_arn)
            run.error_code = "UPLOAD_VALIDATION_FAILED"
            run.safe_to_retry = True  # no CreateJob was attempted
            db.add(run)
            lesson.raw_video_key = key
            lesson.status = "FAILED"
            lesson.error_message = run.error_code
            db.commit()
            raise PipelineError("UPLOAD_VALIDATION_FAILED") from None
        run = _new_run(upload, 0, etag, state="CLAIMED", execution_arn=execution_arn)
        db.add(run)
        lesson.raw_video_key = key
        lesson.status = "PROCESSING"
        lesson.error_message = None
        _clear_previous_content(lesson)
    else:
        run = repo.get_run(db, payload.get("run_id"))
        if (run is None or run.upload_id != upload.id or run.lesson_id != lesson_id
                or lesson.raw_video_key != key or run.attempt != lesson.retry_count):
            return {"decision": "IGNORE"}
        if run.execution_arn:
            return _view(run) if run.execution_arn == execution_arn else {"decision": "IGNORE"}
        if lesson.status != "PROCESSING" or run.state != "QUEUED":
            return {"decision": "IGNORE"}
        try:
            # A failed initial validation is not confirmation. Check original S3
            # write time again on retry; delayed delivery is fine, an expired write
            # must not become valid merely by using a retry event.
            _head_source(storage, upload, etag=run.source_etag, initial=True)
        except Exception:
            run.execution_arn = execution_arn
            run.state = "FAILED"
            run.error_code = "UPLOAD_VALIDATION_FAILED"
            run.safe_to_retry = True
            lesson.status = "FAILED"
            lesson.error_message = run.error_code
            db.commit()
            raise PipelineError("UPLOAD_VALIDATION_FAILED") from None
        run.execution_arn = execution_arn
        run.state = "CLAIMED"
        _clear_previous_content(lesson)
    db.commit()
    logger.info("video_pipeline_claimed lesson_id=%s run_id=%s", lesson.id, run.id)
    return _view(run)


def _owned(db, run_id, execution_arn):
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{64}", run_id):
        raise PipelineError("INVALID_RUN_ID")
    run = repo.get_run(db, run_id)
    if run is None:
        raise PipelineError("RUN_NOT_FOUND")
    lesson = _lock_lesson(db, run.lesson_id)
    # Refresh after obtaining the lesson lock: serializes against retry/recovery.
    db.refresh(run)
    upload = repo.upload_for_run(db, run)
    if (run.execution_arn != execution_arn or run.attempt != lesson.retry_count
            or upload is None or upload.source_key != lesson.raw_video_key
            or lesson.status not in {"PROCESSING", "TRANSCRIBING", "AI_PROCESSING"}):
        raise PipelineError("STALE_EXECUTION")
    return run, lesson, upload


def submit(db, run_id, execution_arn, storage, mediaconvert):
    run, _, upload = _owned(db, run_id, execution_arn)
    if run.job_id and run.state in {"TRANSCODING", "VIDEO_READY"}:
        return {"submitted": True}
    if run.state != "CLAIMED":
        # An earlier call may have reached AWS without a durable response.
        raise PipelineError("SUBMISSION_UNCERTAIN")
    _head_source(storage, upload, etag=run.source_etag)
    request = VideoProcessingRequest(run.lesson_id, run.attempt + 1, upload.source_key)
    run.state = "SUBMITTING"
    run.safe_to_retry = False
    db.commit()  # durable fence BEFORE CreateJob; intentionally no automatic resubmit
    try:
        receipt = mediaconvert.start(request)
    except MediaConvertError as exc:
        if not exc.submission_uncertain:
            run, _, _ = _owned(db, run_id, execution_arn)
            run.safe_to_retry = True
            db.commit()
        raise
    run, _, _ = _owned(db, run_id, execution_arn)
    if run.state != "SUBMITTING":
        raise PipelineError("STALE_EXECUTION")
    run.job_id = receipt.job_id
    run.state = "TRANSCODING"
    db.commit()
    logger.info("video_job_submitted run_id=%s job_id=%s", run.id, run.job_id)
    return {"submitted": True}


def poll(db, run_id, execution_arn, mediaconvert):
    run, _, _ = _owned(db, run_id, execution_arn)
    if not run.job_id or run.state not in {"TRANSCODING", "VIDEO_READY"}:
        raise PipelineError("JOB_NOT_SUBMITTED")
    job = mediaconvert.get_job(run.job_id)
    status = job.get("Status")
    if status in {"ERROR", "CANCELED"}:
        run.safe_to_retry = True
        db.commit()
        return {"status": "FAILED"}
    if status == "COMPLETE":
        run.safe_to_retry = True
        db.commit()
        return {"status": "COMPLETE"}
    if status not in {"SUBMITTED", "PROGRESSING"}:
        raise PipelineError("INVALID_JOB_STATUS")
    return {"status": "WAIT"}


def verify_output(db, run_id, execution_arn, storage, mediaconvert):
    run, lesson, upload = _owned(db, run_id, execution_arn)
    if not run.job_id or mediaconvert.get_job(run.job_id).get("Status") != "COMPLETE":
        raise PipelineError("JOB_NOT_COMPLETE")
    _head_source(storage, upload, etag=run.source_etag)
    metadata = storage.head_video(run.output_key)
    if not isinstance(metadata.get("ContentLength"), int) or metadata["ContentLength"] <= 0:
        raise PipelineError("OUTPUT_MISSING_OR_EMPTY")
    # Expected key is generated from a unique upload/attempt and COMPLETE job;
    # Content-Type may be application/octet-stream from MediaConvert, so do not
    # treat that header alone as media validation. Codec validation belongs to MC.
    run.state = "VIDEO_READY"
    run.safe_to_retry = True
    lesson.processed_video_key = run.output_key
    db.commit()
    return {"video_ready": True, "ai_status": "PENDING"}


def finalize_ai(db, run_id, execution_arn, proof):
    completed = repo.get_run(db, run_id) if isinstance(run_id, str) else None
    if completed is not None and completed.state == "COMPLETE" and completed.execution_arn == execution_arn:
        lesson = lessons_repo.get_by_id(db, completed.lesson_id)
        if (lesson is not None and lesson.retry_count == completed.attempt
                and lesson.processed_video_key == completed.output_key
                and lesson.status in {"REVIEW_REQUIRED", "APPROVED", "PUBLISHED"}):
            return {"status": "REVIEW_REQUIRED"}  # previous finalization committed; no mutation
    run, lesson, _ = _owned(db, run_id, execution_arn)
    if (run.state != "VIDEO_READY" or not isinstance(proof, dict)
            or proof.get("completed") is not True or proof.get("run_id") != run_id
            or lesson.processed_video_key != run.output_key):
        raise PipelineError("AI_NOT_COMPLETE")
    validate_review_content(lesson)
    run.state = "COMPLETE"
    lesson.status = "REVIEW_REQUIRED"
    lesson.error_message = None
    db.commit()
    return {"status": "REVIEW_REQUIRED"}


def fail(db, run_id, execution_arn, *, code="PIPELINE_FAILED"):
    run = repo.get_run(db, run_id)
    if run is None:
        return {"recorded": False}
    lesson = _lock_lesson(db, run.lesson_id)
    db.refresh(run)
    upload = repo.upload_for_run(db, run)
    if (run.execution_arn != execution_arn or run.attempt != lesson.retry_count
            or upload is None or upload.source_key != lesson.raw_video_key
            or run.state in {"COMPLETE", "FAILED"}
            or lesson.status not in {"PROCESSING", "TRANSCRIBING", "AI_PROCESSING"}):
        return {"recorded": False}
    # Never store Error/Cause strings supplied by AWS, the caller or C.
    run.error_code = "WORKFLOW_TERMINATED" if code == "WORKFLOW_TERMINATED" else "PIPELINE_FAILED"
    run.state = "FAILED"
    lesson.status = "FAILED"
    lesson.error_message = run.error_code
    db.commit()
    logger.warning("video_pipeline_failed lesson_id=%s run_id=%s error_code=%s", lesson.id, run.id, run.error_code)
    return {"recorded": True}


class PipelineOutboxProcessor:
    """Retry dispatch is atomic with Lesson update. No external call here."""
    def __init__(self, db):
        self.db = db

    def start(self, request):
        upload = repo.get_upload(self.db, request.source_key)
        if upload is None or upload.lesson_id != request.lesson_id:
            raise ProcessorDispatchError("Upload identity is missing.")
        previous = repo.run_for_attempt(self.db, upload.id, request.attempt - 1)
        if previous is None or previous.state != "FAILED" or not previous.safe_to_retry:
            raise ProcessorDispatchError("Reconcile the previous MediaConvert job before retry.")
        # Caller incremented Lesson.retry_count to request.attempt in its transaction.
        run = _new_run(upload, request.attempt, previous.source_etag)
        self.db.add(run)
        self.db.flush()
        return ProcessingReceipt(request.job_id)


def relay_outbox(db, events_client):
    delivered = 0
    now = _now()
    for run in repo.pending_dispatches(db, now):
        upload = repo.upload_for_run(db, run)
        if upload is None:
            raise PipelineError("UPLOAD_NOT_FOUND")
        result = events_client.put_events(Entries=[{
            "Source": "learncloud.video", "DetailType": "Video Retry Requested",
            "EventBusName": settings.VIDEO_EVENT_BUS,
            "Detail": json.dumps({"kind": "retry", "bucket": settings.S3_BUCKET,
                                  "key": upload.source_key, "run_id": run.id}),
        }])
        if result.get("FailedEntryCount") != 0:
            raise PipelineTemporaryError("EVENT_DELIVERY_FAILED")
        # Keep relaying every 2 minutes until an execution claims the row. EventBridge
        # acceptance alone does not prove target delivery. Duplicate claims are safe.
        run.next_dispatch_at = now + timedelta(minutes=2)
        delivered += 1
    db.commit()
    return {"delivered": delivered}


def reconcile(db, run_id, job_id, mediaconvert):
    """Manual Console recovery only; match job identity, never trust a typed job ID."""
    run = repo.get_run(db, run_id)
    if run is None:
        raise PipelineError("RUN_NOT_FOUND")
    lesson = _lock_lesson(db, run.lesson_id)
    db.refresh(run)
    if run.state != "FAILED" or lesson.status != "FAILED" or run.attempt != lesson.retry_count:
        raise PipelineError("RECONCILE_NOT_ALLOWED")
    upload = repo.upload_for_run(db, run)
    if upload is None or upload.source_key != lesson.raw_video_key:
        raise PipelineError("STALE_EXECUTION")
    request = VideoProcessingRequest(run.lesson_id, run.attempt + 1, upload.source_key)
    expected = mediaconvert.build_job_request(request)["ClientRequestToken"]
    job = mediaconvert.get_job(job_id)
    if job.get("UserMetadata", {}).get("token") != expected:
        raise PipelineError("JOB_IDENTITY_MISMATCH")
    if job.get("Status") not in {"COMPLETE", "ERROR", "CANCELED"}:
        raise PipelineError("JOB_STILL_ACTIVE")
    run.job_id = job_id
    run.safe_to_retry = True
    db.commit()
    return {"safe_to_retry": True}
