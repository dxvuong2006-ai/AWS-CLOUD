from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from botocore.exceptions import BotoCoreError, ClientError

from app.dependencies import get_db, require_instructor
from app.models.user import User
from app.adapters.storage.s3_storage import S3StorageAdapter
from app.services.upload_service import UploadService
from app.schemas.lesson import LessonProcessingStatusResponse


router = APIRouter(
    prefix="/lessons",
    tags=["Uploads"],
)


class UploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    file_size: int = Field(gt=0)


class ConfirmUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")


@router.post("/{lesson_id}/confirm-upload", response_model=LessonProcessingStatusResponse)
def confirm_upload(lesson_id: int, payload: ConfirmUploadRequest,
                   db: Session = Depends(get_db), instructor: User = Depends(require_instructor)):
    return UploadService(S3StorageAdapter()).confirm_upload(db, lesson_id, instructor.id, payload.upload_id)


@router.post("/{lesson_id}/upload-url")
def create_upload_url(
    lesson_id: int,
    payload: UploadUrlRequest,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):

    service = UploadService(
        storage=S3StorageAdapter()
    )

    try:
        return service.create_upload_url(
            db=db,
            lesson_id=lesson_id,
            instructor_id=instructor.id,
            filename=payload.filename,
            content_type=payload.content_type,
            file_size=payload.file_size,
        )

    except ValueError as exc:
        error = str(exc)

        if error == "LESSON_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail="Lesson not found or not owned by instructor",
            )

        raise HTTPException(
            status_code=400,
            detail=error,
        )

    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to generate S3 upload URL",
        ) from exc
