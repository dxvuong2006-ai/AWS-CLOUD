from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class QuestionResponse(BaseModel):
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
    id: int
    section_id: int
    title: str
    passing_score: float
    questions: list[QuestionResponse]

    model_config = ConfigDict(from_attributes=True)


class QuizAnswerSubmit(BaseModel):
    question_id: int
    selected_answer: str


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswerSubmit]


class QuizAttemptResponse(BaseModel):
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
    id: int
    quiz_id: int
    quiz_title: str | None
    score: float
    passed: bool
    attempt_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
