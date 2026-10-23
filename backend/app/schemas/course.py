from pydantic import BaseModel, ConfigDict

# class CourseCreateRequest(BaseModel):
#     title: str
#     description: str | None = None
#     learning_objectives: list[str] | None = None

# chưa có file api-contract.md nên tạm thời định dạng như thế:))
class CourseResponse(BaseModel):
    id: int
    instructor_id: int
    title: str
    description: str | None = None
    learning_objectives: list[str] | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)