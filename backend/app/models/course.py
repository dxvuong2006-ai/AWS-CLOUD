from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON

from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    learning_objectives = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="DRAFT")