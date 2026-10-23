import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./tests.db")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt
from app.models.section import Section
from app.models.user import User


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def quiz_course(db_session):
    user = User(
        cognito_sub="student-1",
        name="Student",
        email="student@example.test",
        role="STUDENT",
    )
    db_session.add(user)
    db_session.flush()

    course = Course(
        instructor_id=user.id,
        title="Course",
        status="PUBLISHED",
    )
    db_session.add(course)
    db_session.flush()

    sections = [
        Section(course_id=course.id, title=f"Section {position}", position=position)
        for position in range(1, 4)
    ]
    db_session.add_all(sections)
    db_session.commit()
    return user, course, sections
