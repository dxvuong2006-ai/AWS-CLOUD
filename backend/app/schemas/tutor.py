#Định nghĩa cấu trúc dữ liệu cho luồng gia sư ảo hỗ trợ học viên khắc phục lỗ hổng kiến thức.
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TutorSessionCreateRequest(BaseModel):
    lesson_id: int
    attempt_id: int | None = None


class TutorMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message content must not be blank")
        return value


class TutorMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: Literal["USER", "ASSISTANT"]
    content: str
    created_at: datetime


class TutorSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    lesson_id: int
    attempt_id: int | None = None
    created_at: datetime


class TutorSessionDetailResponse(TutorSessionResponse):
    messages: list[TutorMessageResponse]