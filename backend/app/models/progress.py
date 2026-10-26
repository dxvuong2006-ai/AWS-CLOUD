from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
    text,
)

from app.database import Base


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        CheckConstraint("watched_seconds >= 0", name="ck_lesson_progress_watched_seconds"),
        UniqueConstraint(
            "student_id",
            "lesson_id",
            name="uq_lesson_progress_student_lesson",
        ),
    )

    id = Column(Integer, primary_key=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lesson_id = Column(
        Integer,
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    watched_seconds = Column(Integer, nullable=False, default=0, server_default=text("0"))
    completed = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )