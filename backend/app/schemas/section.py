from pydantic import BaseModel, ConfigDict, Field


class SectionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    position: int = Field(default=1, ge=1)


class SectionResponse(BaseModel):
    id: int
    course_id: int
    title: str
    position: int

    model_config = ConfigDict(from_attributes=True)
