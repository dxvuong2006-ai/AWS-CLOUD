import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.quizzes import get_course_unlock_status
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.quiz import Quiz
from app.models.section import Section
from app.models.user import User
from app.services import course_service, lesson_service, section_service
from app.services.unlock_service import SectionLockedError


TEST_DATABASE_URL = os.getenv("LEARNCLOUD_TEST_DATABASE_URL")


pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or "15437" in TEST_DATABASE_URL,
    reason="Requires an isolated PostgreSQL test database, never the local RDS tunnel",
)


def test_postgres_guards_enrollment_publish_unlock_and_ownership():
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False)
    db = session_factory()
    instructor = User(
        cognito_sub=f"guard-instructor-{uuid4()}",
        name="Instructor",
        email=f"guard-instructor-{uuid4()}@example.test",
        role="INSTRUCTOR",
    )
    other_instructor = User(
        cognito_sub=f"guard-other-{uuid4()}",
        name="Other",
        email=f"guard-other-{uuid4()}@example.test",
        role="INSTRUCTOR",
    )
    student = User(
        cognito_sub=f"guard-student-{uuid4()}",
        name="Student",
        email=f"guard-student-{uuid4()}@example.test",
        role="STUDENT",
    )
    outsider = User(
        cognito_sub=f"guard-outsider-{uuid4()}",
        name="Outsider",
        email=f"guard-outsider-{uuid4()}@example.test",
        role="STUDENT",
    )
    db.add_all([instructor, other_instructor, student, outsider])
    db.flush()
    course = Course(
        instructor_id=instructor.id, title="Access Guards", status="PUBLISHED"
    )
    db.add(course)
    db.flush()
    first = Section(course_id=course.id, title="First", position=1)
    second = Section(course_id=course.id, title="Second", position=2)
    db.add_all([first, second])
    db.flush()
    db.add_all(
        [
            Lesson(
                section_id=first.id,
                title="Draft",
                position=1,
                status="DRAFT",
            ),
            Lesson(
                section_id=second.id,
                title="Locked published lesson",
                position=1,
                status="PUBLISHED",
                duration_seconds=100,
            ),
            Quiz(section_id=first.id, title="Checkpoint", is_approved=True),
            Enrollment(student_id=student.id, course_id=course.id),
        ]
    )
    db.commit()
    try:
        with pytest.raises(section_service.CourseAccessDeniedError):
            section_service.list_sections_for_course(
                db,
                course_id=course.id,
                user_id=outsider.id,
                user_role="STUDENT",
            )
        with pytest.raises(section_service.CourseAccessDeniedError):
            section_service.list_sections_for_course(
                db,
                course_id=course.id,
                user_id=other_instructor.id,
                user_role="INSTRUCTOR",
            )
        with pytest.raises(SectionLockedError):
            lesson_service.get_lesson_for_user(
                db,
                db.query(Lesson)
                .join(Section, Lesson.section_id == Section.id)
                .filter(
                    Section.course_id == course.id,
                    Lesson.status == "PUBLISHED",
                )
                .one()
                .id,
                user_id=student.id,
                user_role="STUDENT",
            )

        course_detail = course_service.get_course_detail(db, course.id)
        assert all(
            lesson.status == "PUBLISHED"
            for section in course_detail["sections"]
            for lesson in section["lessons"]
        )

        with pytest.raises(HTTPException) as error:
            get_course_unlock_status(course.id, db, outsider)
        assert error.value.status_code == 403
    finally:
        db.rollback()
        db.close()
        engine.dispose()
