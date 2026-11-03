from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.adapters.storage.s3_storage import S3StorageAdapter
from app.adapters.video.base import ProcessorDispatchError, VideoProcessingRequest, VideoProcessor
from app.adapters.video.local_processor import LocalProcessor
from app.config import settings
from app.lesson_states import LessonStatus
from app.repositories import courses_repo, lessons_repo
from app.services import lesson_service
from app.utils.errors import AppError, ConflictError, ExternalServiceError, NotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowUnavailableError(AppError):
    status_code = 503
    code = "WORKFLOW_NOT_CONFIGURED"
    default_message = "Video processing workflow is not configured."


class ProcessingBusyError(ConflictError):
    code = "PROCESSING_BUSY"
    default_message = "Another operation is updating this course or lesson."


class InputVideoNotFoundError(NotFoundError):
    code = "INPUT_VIDEO_NOT_FOUND"
    default_message = "The input video was not found."


class InputStorageError(ExternalServiceError):
    code = "INPUT_STORAGE_UNAVAILABLE"
    default_message = "The input video cannot currently be verified."


class ProcessingDispatchError(AppError):
    status_code = 503
    code = "PROCESSING_DISPATCH_FAILED"
    default_message = "Video processing could not be started."


def get_video_processor(db: Session | None = None) -> VideoProcessor:
    if settings.APP_ENV.strip().lower() == "development" and settings.VIDEO_PROCESSOR_BACKEND == "local":
        return LocalProcessor(settings.LOCAL_VIDEO_JOB_DIR)
    if settings.VIDEO_PIPELINE_ENABLED and settings.VIDEO_PROCESSOR_BACKEND == "eventbridge" and db is not None:
        from app.services.video_pipeline_service import PipelineOutboxProcessor
        return PipelineOutboxProcessor(db)
    raise WorkflowUnavailableError()


def status_response(lesson) -> dict:
    # Stored pipeline messages are untrusted: never forward AWS errors, keys or URLs.
    return {
        "lesson_id": lesson.id,
        "status": lesson.status,
        "retry_count": lesson.retry_count,
        "error_message": "Video processing failed. Please retry or contact support." if lesson.status == LessonStatus.FAILED.value else None,
        "updated_at": lesson.updated_at,
    }


def get_processing_status(db: Session, lesson_id: int, *, user_id: int, user_role: str) -> dict:
    lesson, _ = lesson_service.get_lesson_for_management(
        db, lesson_id, user_id=user_id, user_role=user_role
    )
    return status_response(lesson)


def _verify_input(key: str) -> None:
    try:
        metadata = S3StorageAdapter().head_video(key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        http_status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        logger.warning("Retry input verification failed exception_type=%s", type(exc).__name__)
        if code != "NoSuchBucket" and (code in {"404", "NoSuchKey", "NotFound"} or http_status == 404):
            raise InputVideoNotFoundError() from None
        raise InputStorageError() from None
    except BotoCoreError as exc:
        logger.warning("Retry input verification failed exception_type=%s", type(exc).__name__)
        raise InputStorageError() from None
    if not isinstance(metadata.get("ContentLength"), int) or metadata["ContentLength"] <= 0:
        raise ConflictError("The input video is empty or invalid.", code="INVALID_VIDEO_INPUT")


def retry_lesson(db: Session, lesson_id: int, *, user_id: int, user_role: str) -> dict:
    try:
        lesson, course = lesson_service.get_lesson_for_management(
            db, lesson_id, user_id=user_id, user_role=user_role, allow_admin=True
        )
        # Consistent order with publish: course first, then lessons. Re-read locked data.
        locked_course = courses_repo.lock_by_id(db, course.id)
        if locked_course is None:
            raise lesson_service.CourseNotFoundError("Course not found.")
        if user_role.upper() != "ADMIN" and locked_course.instructor_id != user_id:
            raise lesson_service.CourseOwnershipError("You do not own this course.")
        lesson = lessons_repo.lock_by_id(db, lesson_id)
        if lesson is None:
            raise lesson_service.LessonNotFoundError("Lesson not found.")
        if lesson.status != LessonStatus.FAILED.value:
            raise ConflictError("Only failed lessons can be retried.", code="LESSON_NOT_FAILED")
        if not lesson.raw_video_key or not lesson.raw_video_key.strip():
            raise ConflictError("An input video is required before retry.", code="RAW_VIDEO_REQUIRED")
        processor = get_video_processor(db)
        _verify_input(lesson.raw_video_key)
        request = VideoProcessingRequest(
            lesson_id=lesson.id, attempt=lesson.retry_count + 1, source_key=lesson.raw_video_key
        )
        lessons_repo.begin_retry(db, lesson)
        try:
            receipt = processor.start(request)
            if receipt.job_id != request.job_id:
                raise ProcessorDispatchError("Unexpected processing receipt.")
        except ProcessorDispatchError as exc:
            logger.error("Retry dispatch failed lesson_id=%s exception_type=%s", lesson_id, type(exc).__name__)
            raise ProcessingDispatchError() from None
        db.commit()
        logger.info("Retry accepted reason=failed_lesson lesson_id=%s retry_count=%s job_id=%s", lesson.id, lesson.retry_count, receipt.job_id)
        return status_response(lesson)
    except OperationalError as exc:
        db.rollback()
        if getattr(exc.orig, "pgcode", None) == "55P03":
            raise ProcessingBusyError() from None
        raise
    except Exception:
        db.rollback()
        raise
