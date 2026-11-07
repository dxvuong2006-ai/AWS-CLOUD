from datetime import datetime

from pydantic import BaseModel, ConfigDict
from app.schemas.learning import WatchedRangesRequest


class LessonProgressUpdateRequest(WatchedRangesRequest):
    """Compatibility name for the student watched-range contract."""


class LessonProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    lesson_id: int
    watched_seconds: int
    completed: bool
    updated_at: datetime