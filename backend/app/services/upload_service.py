from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.adapters.storage.base import StorageAdapter
from app.config import settings
from app.utils.errors import ConflictError


ALLOWED_VIDEO_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}

MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 MiB


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

        # Kiểm tra lesson thuộc course của instructor.
        query = text("""
            SELECT l.id
            FROM lessons l
            JOIN sections s ON l.section_id = s.id
            JOIN courses c ON s.course_id = c.id
            WHERE l.id = :lesson_id
              AND c.instructor_id = :instructor_id
        """)

        lesson = db.execute(
            query,
            {
                "lesson_id": lesson_id,
                "instructor_id": instructor_id,
            },
        ).first()

        if lesson is None:
            raise ValueError("LESSON_NOT_FOUND")

        extension = Path(filename).suffix.lower()
        expected_type = ALLOWED_VIDEO_TYPES.get(extension)

        if expected_type is None or content_type != expected_type:
            raise ValueError("INVALID_VIDEO_TYPE")

        if file_size <= 0 or file_size > MAX_VIDEO_SIZE:
            raise ValueError("INVALID_FILE_SIZE")

        upload_id = uuid4().hex
        object_key = (
            f"lessons/{lesson_id}/raw/"
            f"{upload_id}{extension}"
        )
        if settings.VIDEO_PIPELINE_ENABLED:
            from app.repositories import courses_repo, lessons_repo
            from app.services.video_pipeline_service import register_upload
            try:
                lesson_model = lessons_repo.get_by_id(db, lesson_id)
                if lesson_model is None:
                    raise ValueError("LESSON_NOT_FOUND")
                section = lessons_repo.get_section(db, lesson_model.section_id)
                if section is None:
                    raise ValueError("LESSON_NOT_FOUND")
                course = courses_repo.lock_by_id(db, section.course_id)
                lesson_model = lessons_repo.lock_by_id(db, lesson_id)
                if course is None or course.instructor_id != instructor_id:
                    raise ValueError("LESSON_NOT_FOUND")
                if (course.status != "DRAFT" or lesson_model is None
                        or lesson_model.status != "DRAFT" or lesson_model.retry_count != 0):
                    raise ConflictError("A new pipeline upload requires a draft lesson and course.", code="LESSON_NOT_DRAFT")
                register_upload(db, upload_id=upload_id, lesson_id=lesson_id, key=object_key,
                                content_type=content_type, size_bytes=file_size)
                upload_url = self.storage.generate_upload_url(
                    object_key=object_key, content_type=content_type, prevent_overwrite=True,
                )
                db.commit()
            except OperationalError as exc:
                db.rollback()
                if getattr(exc.orig, "pgcode", None) == "55P03":
                    raise ConflictError("Another operation is updating this lesson.", code="UPLOAD_BUSY") from None
                raise
            except Exception:
                db.rollback()
                raise
            return {"upload_url": upload_url, "object_key": object_key, "upload_id": upload_id,
                    "expires_in": 900, "method": "PUT", "content_type": content_type,
                    "required_headers": {"Content-Type": content_type, "If-None-Match": "*"}}
        upload_url = self.storage.generate_upload_url(
            object_key=object_key,
            content_type=content_type,
        )

        return {
            "upload_url": upload_url,
            "object_key": object_key,
            "expires_in": 900,
            "method": "PUT",
            "content_type": content_type,
        }
