from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.lesson_states import LessonStatus


class LessonCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(default=1, ge=1)


class LessonUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=1)


class LessonResponse(BaseModel):
    id: int
    section_id: int
    title: str
    position: int
    model_config = ConfigDict(from_attributes=True)


class LessonVideoUrlResponse(BaseModel):
    lesson_id: int
    video_url: str
    expires_in: int
    content_type: str


class LessonProcessingStatusResponse(BaseModel):
    lesson_id: int
    status: LessonStatus
    retry_count: int = Field(ge=0)
    error_message: str | None = None
    updated_at: datetime


class LessonApprovalResponse(BaseModel):
    lesson_id: int
    status: Literal["APPROVED"]
    updated_at: datetime
