from pydantic import BaseModel, ConfigDict, Field


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