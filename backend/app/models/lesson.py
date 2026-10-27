from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        CheckConstraint("position > 0", name="ck_lessons_position"),
        CheckConstraint(
            "status IN ('DRAFT', 'UPLOADED', 'PROCESSING', 'TRANSCRIBING', "
            "'REVIEW_REQUIRED', 'PUBLISHED', 'FAILED')",
            name="ck_lessons_status",
        ),
        CheckConstraint(
            "jsonb_typeof(key_concepts_json) = 'array'",
            name="ck_lessons_key_concepts_array",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "json_type(key_concepts_json) = 'array'",
            name="ck_lessons_key_concepts_array_sqlite",
        ).ddl_if(dialect="sqlite"),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_lessons_duration_seconds",
        ),
        CheckConstraint("retry_count >= 0", name="ck_lessons_retry_count"),
        UniqueConstraint("section_id", "position", name="uq_lessons_section_position"),
    )

    id = Column(Integer, primary_key=True)
    section_id = Column(
        Integer,
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    position = Column(Integer, nullable=False)

    raw_video_key = Column(Text, nullable=True)
    processed_video_key = Column(Text, nullable=True)

    status = Column(
        String(30),
        nullable=False,
        default="DRAFT",
        server_default=text("'DRAFT'"),
    )

    transcript_json = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    summary = Column(Text, nullable=True)
    key_concepts_json = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    duration_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
