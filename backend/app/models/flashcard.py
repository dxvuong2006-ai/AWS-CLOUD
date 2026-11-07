from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)

from app.database import Base


class Flashcard(Base):
    __tablename__ = "flashcards"
    __table_args__ = (
        CheckConstraint("length(trim(front)) > 0", name="ck_flashcards_front_not_blank"),
        CheckConstraint("length(trim(back)) > 0", name="ck_flashcards_back_not_blank"),
        CheckConstraint("position > 0", name="ck_flashcards_position"),
        UniqueConstraint("lesson_id", "position", name="uq_flashcards_lesson_position"),
    )

    id = Column(Integer, primary_key=True)
    lesson_id = Column(
        Integer,
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    is_approved = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
