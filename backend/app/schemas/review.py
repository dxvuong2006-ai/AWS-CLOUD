#Định nghĩa schema cho quy trình giảng viên kiểm duyệt và biên tập học liệu do AI sinh ra (Human-in-the-loop).
"""Hợp đồng dữ liệu dành riêng cho giảng viên duyệt bản nháp."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel, ConfigDict, Field, StringConstraints, model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Title = Annotated[Text, Field(max_length=255)]
Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ReviewDTO(BaseModel):
    """Cấm trường ngoài hợp đồng và chuẩn hóa chuỗi.

    Vai trò kiến trúc: Pydantic DTO.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class KeyConcept(ReviewDTO):
    """Biểu diễn thuật ngữ và định nghĩa được duyệt.

    Vai trò kiến trúc: Pydantic DTO.
    """

    term: Text
    definition: Text


class ReviewQuestion(ReviewDTO):
    """Biểu diễn câu hỏi dành cho giảng viên, bao gồm đáp án.

    Vai trò kiến trúc: Pydantic DTO.
    """

    question: Text
    options: list[Text] = Field(min_length=2)
    correct_answer: Text
    explanation: Text

    @model_validator(mode="after")
    def check_options(self) -> "ReviewQuestion":
        """Kiểm tra phương án không trùng và chứa đáp án.

        Returns:
            Câu hỏi hợp lệ sau chuẩn hóa chuỗi.
        """
        if len(set(self.options)) != len(self.options):
            raise ValueError("Options must be distinct.")
        if self.correct_answer not in self.options:
            raise ValueError("Correct answer must belong to options.")
        return self


class DraftContent(ReviewDTO):
    """Gom nội dung bài học và đề thi cấp section.

    Vai trò kiến trúc: Pydantic DTO.
    """

    title: Title
    summary: Text
    key_concepts: list[KeyConcept] = Field(min_length=1)
    quiz_title: Title
    questions: list[ReviewQuestion] = Field(min_length=1)


class DraftUpdate(DraftContent):
    """Yêu cầu thay thế bản nháp mà giảng viên đã xem.

    Vai trò kiến trúc: Pydantic DTO.
    """

    expected_revision: Revision


class DraftApproval(ReviewDTO):
    """Xác nhận tường minh phiên bản được giảng viên phê duyệt.

    Vai trò kiến trúc: Pydantic DTO.
    """

    expected_revision: Revision


class DraftGeneration(ReviewDTO):
    """Yêu cầu sinh bản nháp; dự phòng Mock phải bật tường minh.

    Vai trò kiến trúc: Pydantic DTO.
    """

    transcript: Text
    num_questions: int = Field(default=3, ge=1, le=20, strict=True)
    allow_fallback: bool = False


class ReviewResponse(DraftContent):
    """Trả bản nháp và dấu phiên bản cho giảng viên sở hữu khóa học.

    Vai trò kiến trúc: Pydantic DTO.
    """

    lesson_id: int
    section_id: int
    quiz_id: int
    status: Literal["REVIEW_REQUIRED", "PUBLISHED"]
    quiz_approved: bool
    revision: Revision
