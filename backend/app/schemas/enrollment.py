from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnrollmentResponse(BaseModel):
    id: int
    student_id: int
    course_id: int
    enrolled_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyCourseSummary(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: str


class MyCourseEnrollmentResponse(BaseModel):
    course: MyCourseSummary
    status: str
    progress_percent: float
    resume_lesson_id: int | None = None
    unlocked_section_ids: list[int] = []
