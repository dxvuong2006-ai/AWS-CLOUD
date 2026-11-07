from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LessonProgressUpdateRequest(BaseModel):
    watched_seconds: int = Field(ge=0)
    completed: bool | None = None


class LessonProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    lesson_id: int
    watched_seconds: int
    completed: bool
    updated_at: datetime