from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, field_validator
from app.lesson_states import LessonStatus
from app.lesson_video_state import LessonVideoStatus, video_status


class LessonVideoFields(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    status: str | None = None
    has_raw_video: bool = Field(default=False, validation_alias=AliasChoices("has_raw_video", "raw_video_key"))
    has_processed_video: bool = Field(default=False, validation_alias=AliasChoices("has_processed_video", "processed_video_key"))
    upload_pending: bool = False
    pending_upload_id: str | None = None

    @field_validator("has_raw_video", "has_processed_video", mode="before")
    @classmethod
    def video_attached(cls, value):
        return bool(value.strip()) if isinstance(value, str) else bool(value)

    @computed_field
    @property
    def video_status(self) -> LessonVideoStatus:
        return video_status(self.status, self.has_raw_video, self.has_processed_video, self.upload_pending)


class LessonCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(default=1, ge=1)


class LessonUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=1)


class LessonResponse(LessonVideoFields):
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


class LessonProcessingStatusResponse(LessonVideoFields):
    lesson_id: int
    status: LessonStatus
    retry_count: int = Field(ge=0)
    error_message: str | None = None
    updated_at: datetime
