#Quản lý bài kiểm tra và kết quả làm bài
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)

from app.database import Base
from app.models.question import Question  # Giữ tương thích import của Người C.


MIN_PASSING_SCORE = 80.0


class Quiz(Base):
    """Lưu cấu hình bài trắc nghiệm của một chương học.

    Vai trò kiến trúc: SQLAlchemy Model.
    """

    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint(
            "passing_score >= 0 AND passing_score <= 100",
            name="ck_quizzes_passing_score",
        ),
    )

    id = Column(Integer, primary_key=True)
    section_id = Column(
        Integer,
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    title = Column(String(255), nullable=False)
    passing_score = Column(
        Numeric(5, 2),
        nullable=False,
        default=MIN_PASSING_SCORE,
        server_default=text("80.00"),
    )
    is_approved = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class QuizAttempt(Base):
    """Lưu điểm và trạng thái đạt của mỗi lượt nộp bài.

    Vai trò kiến trúc: SQLAlchemy Model.
    """

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_quiz_attempts_score"),
        CheckConstraint("attempt_number > 0", name="ck_quiz_attempts_number"),
        Index("idx_quiz_attempts_student_quiz", "student_id", "quiz_id"),
        UniqueConstraint(
            "student_id",
            "quiz_id",
            "attempt_number",
            name="uq_quiz_attempts_student_quiz_number",
        ),
        UniqueConstraint("student_id", "quiz_id", "request_id",
                         name="uq_quiz_attempts_request"),
    )

    id = Column(Integer, primary_key=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_id = Column(
        Integer,
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    score = Column(Numeric(5, 2), nullable=False)
    passed = Column(Boolean, nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)
    # Nullable for attempts created before checkpoint idempotency was introduced.
    request_id = Column(String(36), nullable=True)
    request_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class QuizAnswer(Base):
    """Lưu lựa chọn và kết quả chấm từng câu trong một lượt thi.

    Vai trò kiến trúc: SQLAlchemy Model.
    """

    __tablename__ = "quiz_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_quiz_answers_attempt_question"),
    )

    id = Column(Integer, primary_key=True)
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
    )
    selected_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CheckpointRemediation(Base):
    """Written only by trusted tutor/review/practice services, never client flags."""

    __tablename__ = "checkpoint_remediation"
    __table_args__ = (
        CheckConstraint("practice_total >= 0 AND practice_total <= 3",
                        name="ck_checkpoint_remediation_total"),
        CheckConstraint("practice_correct >= 0 AND practice_correct <= practice_total",
                        name="ck_checkpoint_remediation_correct"),
    )
    attempt_id = Column(Integer, ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
                        primary_key=True)
    explanation_completed = Column(Boolean, nullable=False, default=False,
                                   server_default=text("false"))
    review_completed = Column(Boolean, nullable=False, default=False,
                              server_default=text("false"))
    practice_total = Column(Integer, nullable=False, default=0, server_default=text("0"))
    practice_correct = Column(Integer, nullable=False, default=0, server_default=text("0"))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now(), onupdate=func.now())

