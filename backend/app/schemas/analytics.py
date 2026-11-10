"""Hợp đồng thống kê bài trắc nghiệm."""
from pydantic import BaseModel


class MissedQuestion(BaseModel):
    """Biểu diễn số lần học viên trả lời sai."""
    question_id: int
    question: str
    incorrect_count: int


class QuizAnalytics(BaseModel):
    """Biểu diễn thống kê theo lượt thi."""
    quiz_id: int
    attempt_count: int
    average_score: float | None
    pass_rate: float
    frequently_missed_questions: list[MissedQuestion]
