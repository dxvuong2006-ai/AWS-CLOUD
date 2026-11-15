from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
import base64
from app.schemas.lesson import LessonVideoFields


class CoverFields(BaseModel):
    cover_image: str | None = Field(default=None, max_length=350000)

    @field_validator("cover_image")
    @classmethod
    def validate_cover(cls, value):
        if value is None:
            return value
        try:
            prefix, encoded = value.split(",", 1)
            data = base64.b64decode(encoded, validate=True)
            valid = ((prefix == "data:image/png;base64" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
                     (prefix == "data:image/jpeg;base64" and data.startswith(b"\xff\xd8\xff")))
            if not valid or len(data) > 256000:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError("Cover must be PNG/JPEG, at most 250 KB")
        return value


class CourseCreateRequest(CoverFields):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    learning_objectives: list[str] = Field(default_factory=list)

class CourseUpdateRequest(CoverFields):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    learning_objectives: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_non_nullable_fields(self) -> "CourseUpdateRequest":
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Title must not be null")
        return self


class CourseLessonResponse(LessonVideoFields):
    id: int
    title: str
    position: int
    duration_seconds: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CourseSectionResponse(BaseModel):
    id: int
    course_id: int
    title: str
    position: int
    lessons: list[CourseLessonResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CourseResponse(CoverFields):
    id: int
    instructor_id: int
    title: str
    description: str | None = None
    learning_objectives: list[str]
    status: str
    created_at: datetime
    updated_at: datetime
    sections: list[CourseSectionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
