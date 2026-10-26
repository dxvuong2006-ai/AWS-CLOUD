from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CourseCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    learning_objectives: list[str] = Field(default_factory=list)

class CourseUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    learning_objectives: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_non_nullable_fields(self) -> "CourseUpdateRequest":
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Title must not be null")
        return self


class CourseLessonResponse(BaseModel):
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


class CourseResponse(BaseModel):
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