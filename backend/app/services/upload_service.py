from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.adapters.storage.base import StorageAdapter
from app.config import settings
from app.models.video_pipeline import VideoUpload
from app.repositories import courses_repo, lessons_repo
from app.adapters.video.mediaconvert import source_identity
from app.utils.errors import ConflictError, ExternalServiceError, NotFoundError, AppError
from botocore.exceptions import BotoCoreError, ClientError


ALLOWED_VIDEO_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}

MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 MiB


class UploadLedgerUnavailable(AppError):
    status_code = 503
    code = "UPLOAD_LEDGER_UNAVAILABLE"
    default_message = "Upload metadata is not ready. Ask an operator to review migration 0005."


def ledger_available(db):
    if "upload_ledger_available" not in db.info:
        db.info["upload_ledger_available"] = inspect(db.connection()).has_table("video_uploads")
    return db.info["upload_ledger_available"]


def pending_upload_metadata(db, lesson):
    if lesson.status != "DRAFT" or lesson.raw_video_key or lesson.processed_video_key or not ledger_available(db):
        return {"upload_pending": False, "pending_upload_id": None}
    ids = [row[0] for row in db.query(VideoUpload.id).filter_by(lesson_id=lesson.id).limit(2).all()]
    return {"upload_pending": bool(ids), "pending_upload_id": ids[0] if len(ids) == 1 else None}


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _check_upload_identity(upload, lesson_id):
    try:
        _, key_upload_id = source_identity(upload.source_key, lesson_id)
        if key_upload_id != upload.id:
            raise ValueError()
    except ValueError:
        raise ConflictError("Stored upload identity needs operator review.", code="UPLOAD_REVIEW_REQUIRED") from None


class UploadService:

    def __init__(self, storage: StorageAdapter):
        self.storage = storage

    def create_upload_url(
        self,
        db: Session,
        lesson_id: int,
        instructor_id: int,
        filename: str,
        content_type: str,
        file_size: int,
    ) -> dict:

        extension = Path(filename).suffix.lower()
        expected_type = ALLOWED_VIDEO_TYPES.get(extension)

        if expected_type is None or content_type != expected_type:
            raise ValueError("INVALID_VIDEO_TYPE")

        if file_size <= 0 or file_size > MAX_VIDEO_SIZE:
            raise ValueError("INVALID_FILE_SIZE")

        try:
            lesson, course = self._lock(db, lesson_id, instructor_id)
            if lesson.raw_video_key or lesson.processed_video_key:
                raise ConflictError("This lesson already has a video. Use processing retry, not another upload.", code="VIDEO_ALREADY_ATTACHED")
            if course.status != "DRAFT" or lesson.status != "DRAFT" or lesson.retry_count != 0:
                raise ConflictError("A new upload requires an empty draft lesson and course.", code="LESSON_NOT_DRAFT")
            if not ledger_available(db):
                raise UploadLedgerUnavailable()
            uploads = db.query(VideoUpload).filter_by(lesson_id=lesson_id).populate_existing().limit(2).all()
            if len(uploads) > 1:
                raise ConflictError("Multiple historical uploads need operator review.", code="UPLOAD_REVIEW_REQUIRED")
            upload = uploads[0] if uploads else None
            if upload is not None:
                _check_upload_identity(upload, lesson_id)
            if upload is not None and (upload.content_type != content_type or upload.size_bytes != file_size
                                      or Path(upload.source_key).suffix.lower() != extension):
                raise ConflictError("Resume the reserved file; a different upload requires explicit review.", code="UPLOAD_RESERVED")
            if upload is None:
                # An empty DB row does not prove S3 is empty: the old upload
                # path could create RAW files without any database record.
                try:
                    unlinked_raw = self.storage.has_raw_video_objects(lesson_id)
                except (BotoCoreError, ClientError):
                    raise ExternalServiceError("Unable to verify existing RAW objects; no new upload was issued.",
                                               code="UPLOAD_INVENTORY_UNAVAILABLE") from None
                if unlinked_raw:
                    raise ConflictError("Existing RAW objects need an explicit metadata reconciliation; do not upload again.",
                                        code="UNLINKED_RAW_VIDEO")
                upload_id = uuid4().hex
                upload = VideoUpload(id=upload_id, lesson_id=lesson_id,
                    source_key=f"lessons/{lesson_id}/raw/{upload_id}{extension}",
                    content_type=content_type, size_bytes=file_size)
                db.add(upload)
            # Re-sign the SAME immutable key after a failed/aborted transfer.
            upload.expires_at = datetime.now(timezone.utc) + timedelta(seconds=900)
            db.flush()
            upload_url = self.storage.generate_upload_url(object_key=upload.source_key,
                content_type=content_type, prevent_overwrite=True)
            result = {"upload_url": upload_url, "object_key": upload.source_key, "upload_id": upload.id,
                "expires_in": 900, "method": "PUT", "content_type": content_type,
                "required_headers": {"Content-Type": content_type, "If-None-Match": "*"}}
            db.commit()
            return result
        except OperationalError as exc:
            db.rollback()
            if getattr(exc.orig, "pgcode", None) == "55P03":
                raise ConflictError("Another operation is updating this lesson.", code="UPLOAD_BUSY") from None
            raise
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _lock(db, lesson_id, instructor_id):
        lesson = lessons_repo.get_by_id(db, lesson_id)
        section = lessons_repo.get_section(db, lesson.section_id) if lesson else None
        if section is None:
            raise NotFoundError("Lesson not found or not owned by instructor.")
        course = courses_repo.lock_by_id(db, section.course_id)
        lesson = lessons_repo.lock_by_id(db, lesson_id)
        if course is None or lesson is None or course.instructor_id != instructor_id:
            raise NotFoundError("Lesson not found or not owned by instructor.")
        return lesson, course

    def confirm_upload(self, db, lesson_id, instructor_id, upload_id):
        try:
            lesson, course = self._lock(db, lesson_id, instructor_id)
            if not ledger_available(db):
                raise UploadLedgerUnavailable()
            upload = db.query(VideoUpload).filter_by(id=upload_id, lesson_id=lesson_id).one_or_none()
            if upload is None:
                raise NotFoundError("Upload was not issued for this lesson.", code="UPLOAD_NOT_FOUND")
            _check_upload_identity(upload, lesson_id)
            if lesson.raw_video_key and lesson.raw_video_key != upload.source_key:
                raise ConflictError("A different current video is attached.", code="VIDEO_ALREADY_ATTACHED")
            if not lesson.raw_video_key and (course.status != "DRAFT" or lesson.status != "DRAFT" or lesson.processed_video_key):
                raise ConflictError("The lesson cannot accept this upload.", code="LESSON_NOT_DRAFT")
            try:
                metadata = self.storage.head_video(upload.source_key)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code in {"404", "NoSuchKey", "NotFound"}:
                    raise NotFoundError("The upload is not yet present on S3.", code="UPLOAD_OBJECT_NOT_FOUND") from None
                raise ExternalServiceError("Unable to verify upload storage.", code="UPLOAD_STORAGE_UNAVAILABLE") from None
            except BotoCoreError:
                raise ExternalServiceError("Unable to verify upload storage.", code="UPLOAD_STORAGE_UNAVAILABLE") from None
            modified = metadata.get("LastModified")
            if (metadata.get("ContentLength") != upload.size_bytes or metadata.get("ContentType") != upload.content_type
                    or not metadata.get("ETag") or not isinstance(modified, datetime)
                    or modified.tzinfo is None or not _utc(upload.created_at).replace(microsecond=0) <= modified <= _utc(upload.expires_at)):
                raise ConflictError("Uploaded object does not match the issued upload.", code="UPLOAD_METADATA_MISMATCH")
            if not lesson.raw_video_key:
                lesson.raw_video_key = upload.source_key
                # EventBridge remains the ONLY initial dispatcher when enabled.
                # Preserve DRAFT so the existing event claim can still proceed.
                if not settings.VIDEO_PIPELINE_ENABLED:
                    lesson.status = "UPLOADED"
            db.commit()
            from app.services.processing_service import status_response
            return status_response(lesson)
        except OperationalError as exc:
            db.rollback()
            if getattr(exc.orig, "pgcode", None) == "55P03":
                raise ConflictError("Another operation is updating this lesson.", code="UPLOAD_BUSY") from None
            raise
        except Exception:
            db.rollback()
            raise
