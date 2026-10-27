from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.adapters.storage.base import StorageAdapter


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

        object_key = (
            f"lessons/{lesson_id}/raw/"
            f"{uuid4().hex}{extension}"
        )

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