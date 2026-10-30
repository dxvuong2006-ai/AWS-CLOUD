"""Explicit instructor approval only. Content generation/editing remains C's scope."""
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.adapters.storage.s3_storage import S3StorageAdapter
from app.lesson_states import LessonStatus
from app.repositories import courses_repo, lessons_repo
from app.services import lesson_service
from app.utils.errors import AppError, ConflictError, ExternalServiceError, ForbiddenError, NotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ApprovalSchemaNotReadyError(AppError):
    status_code = 503
    code = "APPROVAL_SCHEMA_NOT_READY"
    default_message = "The Lesson approval schema has not been applied."


class ApprovalStorageError(ExternalServiceError):
    code = "APPROVAL_STORAGE_UNAVAILABLE"
    default_message = "The processed video cannot currently be verified."


def validate_review_content(lesson) -> None:
    # Generic presence/shape checks only. C owns transcript normalization and AI validation.
    if not lesson.processed_video_key or not lesson.processed_video_key.strip():
        raise ConflictError("A processed video is required for approval.", code="PROCESSED_VIDEO_REQUIRED")
    if not isinstance(lesson.transcript_json, (dict, list)) or not lesson.transcript_json:
        raise ConflictError("A non-empty transcript is required for approval.", code="REVIEW_CONTENT_INCOMPLETE")
    if not isinstance(lesson.summary, str) or not lesson.summary.strip():
        raise ConflictError("A summary is required for approval.", code="REVIEW_CONTENT_INCOMPLETE")
    if not isinstance(lesson.key_concepts_json, list) or not lesson.key_concepts_json:
        raise ConflictError("Key concepts are required for approval.", code="REVIEW_CONTENT_INCOMPLETE")


def _verify_processed_video(key: str) -> None:
    try:
        metadata = S3StorageAdapter().head_video(key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        logger.warning("Approval video verification failed exception_type=%s", type(exc).__name__)
        if code != "NoSuchBucket" and (code in {"404", "NoSuchKey", "NotFound"} or status == 404):
            raise ConflictError("The processed video was not found.", code="PROCESSED_VIDEO_NOT_FOUND") from None
        raise ApprovalStorageError() from None
    except BotoCoreError as exc:
        logger.warning("Approval video verification failed exception_type=%s", type(exc).__name__)
        raise ApprovalStorageError() from None
    if not isinstance(metadata.get("ContentLength"), int) or metadata["ContentLength"] <= 0:
        raise ConflictError("The processed video is empty or invalid.", code="INVALID_PROCESSED_VIDEO")


def _response(lesson) -> dict:
    return {"lesson_id": lesson.id, "status": lesson.status, "updated_at": lesson.updated_at}


def approve_lesson(db: Session, lesson_id: int, *, instructor_id: int) -> dict:
    try:
        lesson, course = lesson_service.get_lesson_for_management(
            db, lesson_id, user_id=instructor_id, user_role="INSTRUCTOR"
        )
        # Same order as retry/publish, including re-reading under the row lock.
        course = courses_repo.lock_by_id(db, course.id)
        if course is None:
            raise NotFoundError("Course not found.")
        if course.instructor_id != instructor_id:
            raise ForbiddenError("You do not own this course.")
        lesson = lessons_repo.lock_by_id(db, lesson_id)
        if lesson is None:
            raise NotFoundError("Lesson not found.")
        if lesson.status == LessonStatus.APPROVED.value:
            db.commit()
            return _response(lesson)
        if course.status != "DRAFT":
            raise ConflictError("New approvals require a draft course.", code="COURSE_NOT_DRAFT")
        if lesson.status != LessonStatus.REVIEW_REQUIRED.value:
            raise ConflictError("Only lessons awaiting review can be approved.", code="LESSON_NOT_REVIEWABLE")
        validate_review_content(lesson)
        if not lessons_repo.approval_schema_ready(db):
            raise ApprovalSchemaNotReadyError()
        _verify_processed_video(lesson.processed_video_key)
        lessons_repo.mark_approved(db, lesson)
        db.commit()
        logger.info("Lesson approved lesson_id=%s instructor_id=%s", lesson.id, instructor_id)
        return _response(lesson)
    except (lesson_service.LessonNotFoundError, lesson_service.SectionNotFoundError, lesson_service.CourseNotFoundError) as exc:
        db.rollback()
        raise NotFoundError(str(exc)) from None
    except (lesson_service.CourseOwnershipError, lesson_service.LessonAccessDeniedError) as exc:
        db.rollback()
        raise ForbiddenError(str(exc)) from None
    except OperationalError as exc:
        db.rollback()
        if getattr(exc.orig, "pgcode", None) == "55P03":
            raise ConflictError("Another operation is updating this course or lesson.", code="REVIEW_BUSY") from None
        raise
    except Exception:
        db.rollback()
        raise
