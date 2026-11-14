import os
import re

from sqlalchemy.orm import Session
from botocore.exceptions import BotoCoreError, ClientError

from app.adapters.storage.s3_storage import S3StorageAdapter
from app.config import settings
from app.models.lesson import Lesson
from app.repositories import lessons_repo
from app.utils.errors import ConflictError, ExternalServiceError, NotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _log_video_storage_error(exc, *, lesson_id: int, storage) -> None:
    """Log diagnostic fields only: AWS messages/tracebacks can contain signed URLs."""
    def label(value):
        value = str(value) if value is not None else "unknown"
        return value if re.fullmatch(r"[A-Za-z0-9._:/-]{1,128}", value) else "redacted"

    metadata = exc.response.get("ResponseMetadata", {}) if isinstance(exc, ClientError) else {}
    aws_code = exc.response.get("Error", {}).get("Code") if isinstance(exc, ClientError) else None
    client = storage.client if storage is not None else None
    logger.error(
        "S3 video playback failed lesson_id=%s pid=%s operation=%s "
        "exception_type=%s aws_code=%s aws_status=%s bucket=%s region=%s "
        "session_profile=%s process_profile=%s",
        lesson_id,
        os.getpid(),
        label(storage.playback_operation if storage is not None else "CreateS3Client"),
        type(exc).__name__,
        label(aws_code),
        label(metadata.get("HTTPStatusCode")),
        label(storage.bucket if storage is not None else settings.S3_BUCKET),
        label(client.meta.region_name if client is not None else settings.AWS_REGION),
        label(storage.profile_name if storage is not None else None),
        label(os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE") or "default"),
        exc_info=False,
    )
from app.repositories import lessons_repo, review_repo
from app.services import unlock_service


class LessonNotFoundError(Exception):
    pass


class SectionNotFoundError(Exception):
    pass


class CourseNotFoundError(Exception):
    pass


class CourseOwnershipError(Exception):
    pass


class PublishedCourseRequiredError(Exception):
    pass


class LessonAccessDeniedError(Exception):
    pass


class VideoNotAvailableError(NotFoundError):
    code = "VIDEO_NOT_AVAILABLE"
    default_message = "This lesson has no video available."


class VideoObjectNotFoundError(NotFoundError):
    code = "VIDEO_OBJECT_NOT_FOUND"
    default_message = "The lesson video object was not found."


class VideoFormatError(ConflictError):
    code = "VIDEO_FORMAT_UNSUPPORTED"
    default_message = "The lesson video is not an MP4 file."


class VideoStorageAccessError(ExternalServiceError):
    code = "VIDEO_STORAGE_ACCESS_DENIED"
    default_message = "Video storage denied access to the lesson video."


class VideoStorageError(ExternalServiceError):
    code = "VIDEO_STORAGE_UNAVAILABLE"
    default_message = "Video storage is temporarily unavailable."


def get_video_url_for_user(
    db: Session, lesson_id: int, *, user_id: int, user_role: str
) -> dict:
    lesson = get_lesson_for_user(
        db, lesson_id, user_id=user_id, user_role=user_role
    )
    key = lesson.processed_video_key
    if not key and (
        settings.APP_ENV.strip().lower() == "development"
        and settings.ALLOW_RAW_VIDEO_PLAYBACK
    ):
        key = lesson.raw_video_key
    if not key:
        raise VideoNotAvailableError()
    if not key.lower().endswith(".mp4"):
        raise VideoFormatError()

    content_type = "video/mp4"
    storage = None
    try:
        storage = S3StorageAdapter()
        video_url = storage.generate_download_url(
            object_key=key,
            content_type=content_type,
            expires_in=settings.VIDEO_URL_EXPIRES_IN,
        )
    except ClientError as exc:
        _log_video_storage_error(exc, lesson_id=lesson.id, storage=storage)
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        # A missing bucket is a storage/configuration failure, not a missing video.
        if code == "NoSuchBucket":
            raise VideoStorageError() from None
        if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
            raise VideoObjectNotFoundError() from None
        if code in {"403", "AccessDenied", "Forbidden"} or status == 403:
            raise VideoStorageAccessError() from None
        raise VideoStorageError() from None
    except BotoCoreError as exc:
        _log_video_storage_error(exc, lesson_id=lesson.id, storage=storage)
        raise VideoStorageError() from None

    return {
        "lesson_id": lesson.id,
        "video_url": video_url,
        "expires_in": settings.VIDEO_URL_EXPIRES_IN,
        "content_type": content_type,
    }

# lấy section và course của 1 lesson
def _get_section_and_course(db: Session, section_id: int):
    section = lessons_repo.get_section(db, section_id)
    if section is None:
        raise SectionNotFoundError("Section not found.")

    course = lessons_repo.get_course(db, section.course_id)
    if course is None:
        raise CourseNotFoundError("Course not found.")

    return section, course

# tạo lesson
def create_lesson(
    db: Session,
    *,
    section_id: int,
    instructor_id: int,
    title: str,
    position: int = 1,
) -> Lesson:
    _, course = _get_section_and_course(db, section_id)

    if course.instructor_id != instructor_id:
        raise CourseOwnershipError("You do not own this course.")

    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("Lesson title must not be blank.")

    return lessons_repo.create(
        db,
        section_id=section_id,
        title=normalized_title,
        position=position,
    )

# kiểm tra quyền truy cập lesson
def _check_lesson_access(
    db: Session, course, *, section_id: int, user_id: int, user_role: str
) -> None:
    role = user_role.upper()
    if role == "INSTRUCTOR":
        if course.instructor_id != user_id:
            raise CourseOwnershipError("You do not own this course.")
        return

    if role != "STUDENT":
        raise LessonAccessDeniedError("You do not have access to this lesson.")

    if str(course.status).upper() != "PUBLISHED":
        raise PublishedCourseRequiredError("Lesson is not available.")
    if not lessons_repo.has_enrollment(
        db, student_id=user_id, course_id=course.id
    ):
        raise LessonAccessDeniedError("You are not enrolled in this course.")
    unlock_service.assert_section_unlocked(
        db,
        student_id=user_id,
        course_id=course.id,
        section_id=section_id,
    )

# lấy lesson cho người dùng
def get_lesson_for_user(
    db: Session, lesson_id: int, *, user_id: int, user_role: str
) -> Lesson:
    lesson = lessons_repo.get_by_id(db, lesson_id)
    if lesson is None:
        raise LessonNotFoundError("Lesson not found.")

    _, course = _get_section_and_course(db, lesson.section_id)
    _check_lesson_access(
        db, course, section_id=lesson.section_id, user_id=user_id, user_role=user_role
    )

    if user_role.upper() == "STUDENT" and lesson.status not in (
        "PUBLISHED",
    ):
        raise LessonAccessDeniedError("Lesson is awaiting instructor approval.")
    return lesson


def get_lesson_for_management(
    db: Session, lesson_id: int, *, user_id: int, user_role: str, allow_admin: bool = False
):
    lesson = lessons_repo.get_by_id(db, lesson_id)
    if lesson is None:
        raise LessonNotFoundError("Lesson not found.")
    _, course = _get_section_and_course(db, lesson.section_id)
    if allow_admin and user_role.upper() == "ADMIN":
        return lesson, course
    if user_role.upper() != "INSTRUCTOR":
        raise LessonAccessDeniedError("Instructor role required.")
    _check_lesson_access(
        db, course, section_id=section_id, user_id=user_id, user_role=user_role
    )
    return lesson, course

# cập nhật lesson
def update_lesson(
    db: Session, *, lesson_id: int, instructor_id: int, changes: dict
) -> Lesson:
    lesson = lessons_repo.get_by_id(db, lesson_id)
    if lesson is None:
        raise LessonNotFoundError("Lesson not found.")

    _, course = _get_section_and_course(db, lesson.section_id)
    if course.instructor_id != instructor_id:
        raise CourseOwnershipError("You do not own this course.")

    safe_changes = {
        key: value
        for key, value in changes.items()
        if key in {"title", "position"} and value is not None
    }
    if "title" in safe_changes:
        safe_changes["title"] = safe_changes["title"].strip()
        if not safe_changes["title"]:
            raise ValueError("Lesson title must not be blank.")

    return lessons_repo.update(db, lesson, safe_changes)

# lấy danh sách lessons của 1 section
def list_lessons_for_section(
    db: Session,
    section_id: int,
    *,
    user_id: int,
    user_role: str,
    skip: int = 0,
    limit: int = 100,
) -> list[Lesson]:
    _, course = _get_section_and_course(db, section_id)
    _check_lesson_access(
        db, course, section_id=section_id, user_id=user_id, user_role=user_role
    )
    if user_role.upper() == "STUDENT":
        return review_repo.list_visible_lessons(
            db, section_id, skip=skip, limit=limit,
        )
    return lessons_repo.get_by_section(db, section_id, skip=skip, limit=limit)
