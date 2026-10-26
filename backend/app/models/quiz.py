from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


MIN_PASSING_SCORE = 80.0


class Quiz(Base):
    """Lưu cấu hình bài trắc nghiệm của một chương học.

    Vai trò kiến trúc: SQLAlchemy Model.
    """

    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(
        Integer,
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    passing_score = Column(Float, default=MIN_PASSING_SCORE, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)


class Question(Base):
    """Lưu câu hỏi, lựa chọn và đáp án của bài trắc nghiệm.

    Vai trò kiến trúc: SQLAlchemy Model.
    """

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(
        Integer,
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question = Column(Text, nullable=False)
    options_json = Column(JSON, nullable=False)
    correct_answer = Column(String(500), nullable=False)
    explanation = Column(Text, nullable=True)
    position = Column(Integer, default=1, nullable=False)


class QuizAttempt(Base):
    """Lưu điểm và trạng thái đạt của mỗi lượt nộp bài.

    Vai trò kiến trúc: SQLAlchemy Model.
    """

    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quiz_id = Column(
        Integer,
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score = Column(Float, nullable=False)
    passed = Column(Boolean, nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class QuizAnswer(Base):
    """Lưu lựa chọn và kết quả chấm từng câu trong một lượt thi.

    Vai trò kiến trúc: SQLAlchemy Model.
    """

    __tablename__ = "quiz_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(
        Integer,
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    selected_answer = Column(String(500), nullable=False)
    is_correct = Column(Boolean, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_quiz_attempt_question",
        ),
    )
