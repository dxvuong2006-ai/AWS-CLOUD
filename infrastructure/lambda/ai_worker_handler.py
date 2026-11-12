"""Dedicated K5 Lambda entrypoint.  It is intentionally separate from K4."""

import logging

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import OperationalError

from app.adapters.ai.bedrock_ai import BedrockAIAdapter
from app.adapters.transcription.aws_transcribe import AWSTranscribeAdapter
from app.adapters.transcription.s3_transcript import S3TranscriptAdapter
from app.config import settings
from app.database import SessionLocal
from app.services import ai_worker_service as service

logger = logging.getLogger(__name__)


def _enabled():
    if not settings.AI_WORKER_ENABLED:
        raise service.AIWorkerError("AI_WORKER_DISABLED")
    if settings.AWS_REGION != "ap-southeast-1":
        raise service.AIWorkerError("INVALID_AI_WORKER_REGION")


def _execute(event, db):
    action = event.get("action")
    run_id, owner = event.get("run_id"), event.get("execution_arn")
    transcriber = AWSTranscribeAdapter()
    if action == "start_transcription":
        return service.start_transcription(db, run_id, owner, transcriber)
    if action == "poll_transcription":
        return service.poll_transcription(
            db, run_id, owner, event.get("job_id"), transcriber,
        )
    if action == "generate_content":
        return service.generate_content(
            db, run_id, owner, event.get("job_id"),
            transcriber=transcriber,
            transcript_store=S3TranscriptAdapter(),
            ai=BedrockAIAdapter(allow_fallback=False),
        )
    raise service.AIWorkerError("INVALID_AI_WORKER_ACTION")


def handler(event, context):
    try:
        _enabled()
        with SessionLocal() as db:
            if not isinstance(event, dict):
                raise service.AIWorkerError("INVALID_AI_WORKER_INPUT")
            return _execute(event, db)
    except Exception as exc:
        safe_code = (
            str(exc) if isinstance(exc, service.AIWorkerError)
            else "AI_WORKER_OPERATION_FAILED"
        )
        action = event.get("action", "invalid") if isinstance(event, dict) else "invalid"
        run_id = event.get("run_id", "invalid") if isinstance(event, dict) else "invalid"
        if action not in {"start_transcription", "poll_transcription", "generate_content"}:
            action = "invalid"
        if (
            not isinstance(run_id, str)
            or len(run_id) != 64
            or any(character not in "0123456789abcdef" for character in run_id)
        ):
            run_id = "invalid"
        logger.warning(
            "ai_worker_operation_failed action=%s run_id=%s code=%s type=%s",
            action, run_id, safe_code, type(exc).__name__,
        )
        if isinstance(exc, service.AIWorkerTemporaryError):
            raise service.AIWorkerTemporaryError(safe_code) from None
        if isinstance(exc, ClientError):
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
            code = exc.response.get("Error", {}).get("Code", "")
            if status >= 500 or status == 429 or code in {
                "ThrottlingException", "TooManyRequestsException",
                "LimitExceededException", "InternalFailure",
                "InternalFailureException", "ServiceUnavailableException",
                "ModelNotReadyException", "ModelTimeoutException",
            }:
                raise service.AIWorkerTemporaryError(
                    "AI_WORKER_DEPENDENCY_UNAVAILABLE"
                ) from None
        if isinstance(exc, (OperationalError, BotoCoreError)):
            raise service.AIWorkerTemporaryError(
                "AI_WORKER_DEPENDENCY_UNAVAILABLE"
            ) from None
        raise service.AIWorkerError(safe_code) from None
