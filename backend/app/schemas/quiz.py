#Định nghĩa hợp đồng dữ liệu (Data Transfer Objects - DTO) cho luồng làm bài thi và kiểm tra mở khóa bài học.
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    AliasChoices, BaseModel, ConfigDict, Field, model_validator,
)


class QuizCreateRequest(BaseModel):
    section_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    passing_score: Decimal = Field(default=Decimal("80.00"), ge=0, le=100)



class QuizUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    passing_score: Decimal | None = Field(default=None, ge=0, le=100)



class QuestionCreateRequest(BaseModel):
    question: str = Field(min_length=1)
    options_json: list[str] = Field(min_length=2)
    correct_answer: str = Field(min_length=1)
    explanation: str | None = None
    topic: str | None = Field(default=None, max_length=255)
    source_start_seconds: Decimal | None = Field(default=None, ge=0)
    source_end_seconds: Decimal | None = Field(default=None, ge=0)
    position: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_question_data(self) -> "QuestionCreateRequest":
        question = self.question.strip()
        options = [option.strip() for option in self.options_json]
        if not self.question.strip():
            raise ValueError("Question must not be blank")
        if any(not option for option in options):
            raise ValueError("Options must not be blank")
        if len(set(options)) != len(options):
            raise ValueError("Options must be unique")
        if self.correct_answer.strip() not in options:
            raise ValueError("Correct answer must match one of the options")
        if (
            self.source_start_seconds is None
        ) != (
            self.source_end_seconds is None
        ):
            raise ValueError("Source start and end must be provided together")
        if (
            self.source_start_seconds is not None
            and self.source_end_seconds is not None
            and self.source_end_seconds < self.source_start_seconds
        ):
            raise ValueError("Source end must not be earlier than source start")
        self.question = question
        self.options_json = options
        self.correct_answer = self.correct_answer.strip()
        return self


class QuestionResponse(BaseModel):
    """Public question DTO. Review-only fields are excluded."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    question: str
    options: list[str] = Field(
        validation_alias=AliasChoices("options", "options_json"),
        serialization_alias="options",
    )
    position: int

class QuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    title: str
    passing_score: Decimal
    is_approved: bool
    created_at: datetime
    updated_at: datetime


class QuizDetailResponse(QuizResponse):
    questions: list[QuestionResponse]
    attempt_count: int = 0
    previous_score: Decimal | None = None
    can_retry: bool = True


class QuizAnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: int = Field(gt=0)
    selected_answer: str | None = None

class QuizSubmitRequest(BaseModel):
    """Canonical replay-protected checkpoint submission contract."""

    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    lesson_id: int | None = Field(default=None, gt=0)
    answers: list[QuizAnswerSubmit] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_questions(self) -> "QuizSubmitRequest":
        question_ids = [answer.question_id for answer in self.answers]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Each question may only be answered once")
        return self


# Backward-compatible import name; both paths now enforce the same request ID.
QuizAttemptSubmitRequest = QuizSubmitRequest



class QuizAnswerResult(BaseModel):
    question_id: int
    selected_answer: str | None = None
    is_correct: bool



class QuizAttemptResponse(BaseModel):
    """Public attempt metadata without answer keys or explanations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    quiz_id: int
    score: Decimal
    passed: bool
    attempt_number: int
    created_at: datetime


class QuizAttemptResultResponse(QuizAttemptResponse):
    answers: list[QuizAnswerResult]
    can_retry: bool
    remediation_required: bool



class QuizAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt_id: int
    question_id: int
    selected_answer: str | None = None
    is_correct: bool
    created_at: datetime


class QuestionReviewResponse(BaseModel):
    """Full question DTO for instructor review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    question: str
    options_json: list[str]
    explanation: str | None = None
    topic: str | None = None
    source_start_seconds: Decimal | None = None
    source_end_seconds: Decimal | None = None
    position: int
    created_at: datetime
    correct_answer: str


class QuizHistoryItemResponse(BaseModel):
    """One student-owned attempt in paginated quiz history."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_id: int
    quiz_title: str | None
    score: float
    passed: bool
    attempt_number: int
    created_at: datetime
