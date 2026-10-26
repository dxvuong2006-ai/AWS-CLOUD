from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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
