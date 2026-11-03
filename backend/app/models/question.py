from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("length(trim(question)) > 0", name="ck_questions_not_blank"),
        CheckConstraint(
            "jsonb_typeof(options_json) = 'array' "
            "AND jsonb_array_length(options_json) >= 2",
            name="ck_questions_options_array",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "(source_start_seconds IS NULL AND source_end_seconds IS NULL) OR "
            "(source_start_seconds IS NOT NULL AND source_end_seconds IS NOT NULL "
            "AND source_start_seconds >= 0 "
            "AND source_end_seconds >= source_start_seconds)",
            name="ck_questions_source_range",
        ),
        CheckConstraint(
            "options_json ? correct_answer",
            name="ck_questions_correct_answer_in_options",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "json_type(options_json) = 'array' "
            "AND json_array_length(options_json) >= 2",
            name="ck_questions_options_array_sqlite",
        ).ddl_if(dialect="sqlite"),
        CheckConstraint("position > 0", name="ck_questions_position"),
        UniqueConstraint("quiz_id", "position", name="uq_questions_quiz_position"),
    )

    id = Column(Integer, primary_key=True)
    quiz_id = Column(
        Integer,
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    question = Column(Text, nullable=False)
    options_json = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    topic = Column(String(255), nullable=True)
    source_start_seconds = Column(Numeric(10, 3), nullable=True)
    source_end_seconds = Column(Numeric(10, 3), nullable=True)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())