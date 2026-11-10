"""Student learning wire contract. Runtime endpoints remain a separate implementation."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0, allow_inf_nan=False)
    text: str


class LearningContentResponse(BaseModel):
    id: int
    section_id: int
    title: str
    video_url: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    summary: str = ""
    transcript: list[TranscriptSegment] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)


class WatchedRangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_position_seconds: float = Field(ge=0, allow_inf_nan=False)
    watched_ranges: list[tuple[float, float]] = Field(max_length=5000)

    @model_validator(mode="after")
    def validate_ranges(self):
        import math
        for start, end in self.watched_ranges:
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
                raise ValueError("Each watched range must have finite 0 <= start < end")
        return self


class StudentLessonProgress(BaseModel):
    lesson_id: int
    progress_percent: float = Field(ge=0, le=100)
    completed: bool
    last_position_seconds: float = Field(ge=0)
    watched_seconds: float = Field(ge=0)
    watched_ranges: list[tuple[float, float]] = Field(default_factory=list)


class CourseProgressResponse(BaseModel):
    course_id: int
    overall_percent: float = Field(ge=0, le=100)
    lessons: list[StudentLessonProgress]
