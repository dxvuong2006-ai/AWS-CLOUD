"""Lambda entrypoints. Disabled by default; SDK clients are created lazily.

Package at zip root alongside app/. Handler errors contain safe codes only.
The service validates the composite upload/lesson identity and execution generation
for callbacks. Upload confirmation remains verified S3 claim, with no confirm API
or confirmed_at field added by migration 0005.
"""
import logging

from botocore.config import Config
from sqlalchemy.exc import OperationalError

from app.adapters.storage.s3_storage import S3StorageAdapter
from app.adapters.video.mediaconvert import MediaConvertAdapter, MediaConvertConfig
from app.config import settings
from app.database import SessionLocal
from app.repositories import video_pipeline_repo as repo
from app.services import video_pipeline_service as service

logger = logging.getLogger(__name__)


def _enabled():
    if not settings.VIDEO_PIPELINE_ENABLED:
        raise service.PipelineError("PIPELINE_DISABLED")


def _mediaconvert():
    return MediaConvertAdapter(MediaConvertConfig(
        settings.S3_BUCKET, settings.MEDIACONVERT_ROLE_ARN,
        settings.AWS_REGION, settings.MEDIACONVERT_QUEUE_ARN,
    ))


def _execute(event, db):
    action = event.get("action")
    if action == "claim":
        return service.claim(db, event.get("payload"), event["execution_arn"], S3StorageAdapter())
    run_id, owner = event.get("run_id"), event.get("execution_arn")
    if action == "submit":
        return service.submit(db, run_id, owner, S3StorageAdapter(), _mediaconvert())
    if action == "poll":
        return service.poll(db, run_id, owner, _mediaconvert())
    if action == "verify":
        return service.verify_output(db, run_id, owner, S3StorageAdapter(), _mediaconvert())
    if action == "finalize_ai":
        if not settings.VIDEO_AI_ENABLED:
            raise service.PipelineError("AI_PIPELINE_DISABLED")
        return service.finalize_ai(db, run_id, owner, event.get("proof"))
    if action == "fail":
        return service.fail(db, run_id, owner)
    if action == "reconcile":
        return service.reconcile(db, run_id, event.get("job_id"), _mediaconvert())
    raise service.PipelineError("INVALID_PIPELINE_ACTION")


def handler(event, context):
    _enabled()
    with SessionLocal() as db:
        try:
            if not isinstance(event, dict):
                raise service.PipelineError("INVALID_PIPELINE_INPUT")
            return _execute(event, db)
        except Exception as exc:
            db.rollback()
            logger.warning("pipeline_operation_failed type=%s", type(exc).__name__)
            if isinstance(exc, OperationalError):
                raise service.PipelineTemporaryError("PIPELINE_DATABASE_UNAVAILABLE") from None
            if (isinstance(event, dict) and event.get("action") in {"poll", "verify"}
                    and getattr(exc, "retryable", False)):
                raise service.PipelineTemporaryError("PIPELINE_READ_UNAVAILABLE") from None
            # Do not let the Lambda runtime log raw SDK/SQL exceptions.
            code = str(exc) if isinstance(exc, service.PipelineError) else "PIPELINE_OPERATION_FAILED"
            raise service.PipelineError(code) from None


def relay_handler(event, context):
    _enabled()
    import boto3
    client = boto3.client("events", region_name=settings.AWS_REGION, config=Config(
        connect_timeout=3, read_timeout=5, retries={"mode": "standard", "total_max_attempts": 2},
    ))
    with SessionLocal() as db:
        try:
            return service.relay_outbox(db, client)
        except Exception:
            db.rollback()
            raise service.PipelineTemporaryError("OUTBOX_RELAY_FAILED") from None


def recovery_handler(event, context):
    """EventBridge Standard execution FAILED/TIMED_OUT/ABORTED cleanup.

    Handles failures outside ASL Catch, including execution timeout/stop. It does
    not resubmit/cancel jobs: an active/unknown job must be reconciled before retry.
    """
    _enabled()
    detail = event.get("detail", {})
    if detail.get("status") not in {"FAILED", "TIMED_OUT", "ABORTED"}:
        return {"recorded": False}
    owner = detail.get("executionArn")
    with SessionLocal() as db:
        try:
            run = repo.run_for_execution(db, owner)
            if run is None:
                return {"recorded": False}
            return service.fail(db, run.id, owner, code="WORKFLOW_TERMINATED")
        except Exception:
            db.rollback()
            raise service.PipelineTemporaryError("RECOVERY_FAILED") from None
