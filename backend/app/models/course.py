from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(learning_objectives) = 'array'",
            name="ck_courses_learning_objectives_array",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED')",
            name="ck_courses_status",
        ),
    )

    id = Column(Integer, primary_key=True)
    instructor_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    learning_objectives = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    status = Column(
        String(20),
        nullable=False,
        default="DRAFT",
        server_default=text("'DRAFT'"),
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )