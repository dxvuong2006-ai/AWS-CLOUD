from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FlashcardCreateRequest(BaseModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    position: int = Field(gt=0)

    @field_validator("front", "back")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Flashcard text must not be blank")
        return value


class FlashcardUpdateRequest(BaseModel):
    front: str | None = Field(default=None, min_length=1)
    back: str | None = Field(default=None, min_length=1)
    position: int | None = Field(default=None, gt=0)
    is_approved: bool | None = None

    @field_validator("front", "back")
    @classmethod
    def validate_non_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Flashcard text must not be blank")
        return value


class FlashcardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lesson_id: int
    front: str
    back: str
    position: int
    is_approved: bool
    created_at: datetime
    updated_at: datetime
