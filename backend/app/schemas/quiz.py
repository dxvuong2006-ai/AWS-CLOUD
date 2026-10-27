from datetime import datetime
from decimal import Decimal

from pydantic import (
    AliasChoices, BaseModel, ConfigDict, Field, model_validator,
)


class QuestionResponse(BaseModel):
    """Biểu diễn câu hỏi cho học viên mà không lộ đáp án.

    Vai trò kiến trúc: Pydantic DTO.
    """

    id: int
    quiz_id: int
    question: str
    options: list[str] = Field(
        validation_alias=AliasChoices("options", "options_json"),
        serialization_alias="options",
    )
    position: int

    model_config = ConfigDict(from_attributes=True)


class QuestionResultResponse(BaseModel):
    """Biểu diễn đáp án và lời giải sau khi nộp bài.

    Vai trò kiến trúc: Pydantic DTO.
    """

    id: int
    quiz_id: int
    question: str
    options: list[str] = Field(
        validation_alias=AliasChoices("options", "options_json"),
        serialization_alias="options",
    )
    selected_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str | None

    model_config = ConfigDict(from_attributes=True)


class QuizDetailResponse(BaseModel):
    """Biểu diễn đề thi với các câu hỏi đã ẩn đáp án.

    Vai trò kiến trúc: Pydantic DTO.
    """

    id: int
    section_id: int
    title: str
    passing_score: float
    questions: list[QuestionResponse]

    model_config = ConfigDict(from_attributes=True)


class QuizAnswerSubmit(BaseModel):
    """Tiếp nhận lựa chọn của học viên cho một câu hỏi.

    Vai trò kiến trúc: Pydantic DTO.
    """

    question_id: int
    selected_answer: str


class QuizSubmitRequest(BaseModel):
    """Tiếp nhận danh sách câu trả lời trong lần nộp bài.

    Vai trò kiến trúc: Pydantic DTO.
    """

    answers: list[QuizAnswerSubmit]


class QuizAttemptResponse(BaseModel):
    """Biểu diễn điểm và chi tiết kết quả một lượt thi.

    Vai trò kiến trúc: Pydantic DTO.
    """

    id: int
    quiz_id: int
    student_id: int
    score: float
    passed: bool
    attempt_number: int
    created_at: datetime
    results: list[QuestionResultResponse] | None = None

    model_config = ConfigDict(from_attributes=True)


class QuizHistoryItemResponse(BaseModel):
    """Biểu diễn một lượt thi trong lịch sử học viên.

    Vai trò kiến trúc: Pydantic DTO.
    """

    id: int
    quiz_id: int
    quiz_title: str | None
    score: float
    passed: bool
    attempt_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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



class QuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    title: str
    passing_score: Decimal
    is_approved: bool
    created_at: datetime
    updated_at: datetime



class QuizAttemptSubmitRequest(BaseModel):
    answers: list[QuizAnswerSubmit] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_questions(self) -> "QuizAttemptSubmitRequest":
        question_ids = [answer.question_id for answer in self.answers]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Each question may only be answered once")
        return self



class QuizAnswerResult(BaseModel):
    question_id: int
    selected_answer: str | None = None
    is_correct: bool



class QuizAttemptResultResponse(QuizAttemptResponse):
    answers: list[QuizAnswerResult]



class QuizAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt_id: int
    question_id: int
    selected_answer: str | None = None
    is_correct: bool
    created_at: datetime


class QuestionReviewResponse(BaseModel):
    """Biểu diễn đầy đủ câu hỏi cho bước duyệt của giảng viên.

    Vai trò kiến trúc: Pydantic DTO.
    """

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
