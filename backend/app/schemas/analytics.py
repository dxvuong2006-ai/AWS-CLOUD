"""Typed responses for instructor quiz analytics."""

from pydantic import BaseModel


class MissedQuestion(BaseModel):
    question_id: int
    question: str
    incorrect_count: int


class QuizAnalytics(BaseModel):
    quiz_id: int
    attempt_count: int
    average_score: float | None
    pass_rate: float
    frequently_missed_questions: list[MissedQuestion]
