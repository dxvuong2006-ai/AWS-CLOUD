from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint

from app.database import Base


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    position = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "position",
            name="uq_sections_course_position",
        ),
    )