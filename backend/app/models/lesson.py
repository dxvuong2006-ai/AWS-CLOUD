from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Text,
    JSON,
)

from app.database import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(
        Integer,
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    position = Column(Integer, nullable=False)

    raw_video_key = Column(String(512), nullable=True)
    processed_video_key = Column(String(512), nullable=True)

    status = Column(
        String(30),
        nullable=False,
        default="DRAFT",
    )

    transcript_json = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    key_concepts_json = Column(JSON, nullable=True)
