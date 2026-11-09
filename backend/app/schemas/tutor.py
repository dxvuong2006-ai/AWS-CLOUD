"""DTO của phiên Tutor và luyện tập."""

from pydantic import BaseModel, ConfigDict, Field


class TutorSessionCreateRequest(BaseModel):
    """Nhận mã lượt thi chưa đạt."""

    model_config = ConfigDict(extra="forbid")
    attempt_id: int = Field(gt=0)


class TutorMessageCreateRequest(BaseModel):
    """Nhận câu hỏi của học viên."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)


class PracticeSubmission(BaseModel):
    """Nhận danh sách đáp án theo thứ tự câu hỏi."""

    model_config = ConfigDict(extra="forbid")
    answers: list[str] = Field(min_length=1)


class QuestionRemediationRequest(BaseModel):
    """Nhận lựa chọn đã nộp để ôn tập một câu hỏi."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    attempt_id: int = Field(gt=0)
    lesson_id: int = Field(gt=0)
    question_id: int = Field(gt=0)
    selected_option: str = Field(min_length=1)
