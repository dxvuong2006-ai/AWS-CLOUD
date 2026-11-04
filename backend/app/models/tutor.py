#Lưu phiên trợ lý AI kèm học
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from app.database import Base


class TutorSession(Base):
    __tablename__ = "tutor_sessions"

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
    attempt_id = Column(
        Integer,
        ForeignKey("quiz_attempts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TutorMessage(Base):
    __tablename__ = "tutor_messages"
    __table_args__ = (
        CheckConstraint("role IN ('USER', 'ASSISTANT')", name="ck_tutor_messages_role"),
        CheckConstraint(
            "length(trim(content)) > 0",
            name="ck_tutor_messages_content_not_blank",
        ),
    )

    id = Column(Integer, primary_key=True)
    session_id = Column(
        Integer,
        ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())