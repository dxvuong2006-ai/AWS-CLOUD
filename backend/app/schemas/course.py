from pydantic import BaseModel, ConfigDict, Field

class CourseCreateRequest(BaseModel):
    title: str
    description: str | None = None
    learning_objectives: list[str] | None = None

class CourseUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    learning_objectives: list[str] | None = None

class CourseResponse(BaseModel):
    id: int
    instructor_id: int
    title: str
    description: str | None = None
    learning_objectives: list[str] | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)