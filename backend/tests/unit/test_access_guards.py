import pytest
from fastapi import HTTPException

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.quiz import Quiz
from app.models.section import Section
from app.models.user import User
from app.api.progress import start_viewing_session
from app.services import course_service, lesson_service, section_service
from app.services.unlock_service import SectionLockedError


def _course(db_session):
    instructor = User(
        cognito_sub="guard-instructor",
        name="Instructor",
        email="guard-instructor@example.test",
        role="INSTRUCTOR",
    )
    student = User(
        cognito_sub="guard-student",
        name="Student",
        email="guard-student@example.test",
        role="STUDENT",
    )
    db_session.add_all([instructor, student])
    db_session.flush()
    course = Course(instructor_id=instructor.id, title="Guarded", status="PUBLISHED")
    db_session.add(course)
    db_session.flush()
    first = Section(course_id=course.id, title="First", position=1)
    second = Section(course_id=course.id, title="Second", position=2)
    db_session.add_all([first, second])
    db_session.flush()
    locked_lesson = Lesson(
        section_id=second.id,
        title="Locked",
        position=1,
        status="PUBLISHED",
        duration_seconds=100,
    )
    draft_lesson = Lesson(
        section_id=first.id,
        title="Draft",
        position=2,
        status="DRAFT",
    )
    db_session.add_all([locked_lesson, draft_lesson])
    db_session.add(Quiz(section_id=first.id, title="Checkpoint", is_approved=True))
    db_session.add(Enrollment(student_id=student.id, course_id=course.id))
    db_session.commit()
    return instructor, student, course, first, second, locked_lesson


def test_student_sections_require_enrollment_and_instructor_ownership(db_session):
    instructor, student, course, first, _, _ = _course(db_session)

    outsider = User(
        cognito_sub="guard-outsider",
        name="Outsider",
        email="guard-outsider@example.test",
        role="STUDENT",
    )
    other_instructor = User(
        cognito_sub="guard-other-instructor",
        name="Other Instructor",
        email="guard-other-instructor@example.test",
        role="INSTRUCTOR",
    )
    db_session.add_all([outsider, other_instructor])
    db_session.commit()

    with pytest.raises(section_service.CourseAccessDeniedError):
        section_service.list_sections_for_course(
            db_session,
            course_id=course.id,
            user_id=outsider.id,
            user_role="STUDENT",
        )
    with pytest.raises(section_service.CourseAccessDeniedError):
        section_service.list_sections_for_course(
            db_session,
            course_id=course.id,
            user_id=other_instructor.id,
            user_role="INSTRUCTOR",
        )
    assert section_service.list_sections_for_course(
        db_session,
        course_id=course.id,
        user_id=student.id,
        user_role="STUDENT",
    )[0].id == first.id


def test_student_cannot_read_locked_lesson_or_unpublished_lesson(db_session):
    _, student, course, _, _, locked_lesson = _course(db_session)

    with pytest.raises(SectionLockedError):
        lesson_service.get_lesson_for_user(
            db_session,
            locked_lesson.id,
            user_id=student.id,
            user_role="STUDENT",
        )

    detail = course_service.get_course_detail(db_session, course.id)
    lesson_titles = [
        lesson.title
        for section in detail["sections"]
        for lesson in section["lessons"]
    ]
    assert "Draft" not in lesson_titles


def test_progress_cannot_start_for_locked_lesson(db_session):
    _, student, _, _, _, locked_lesson = _course(db_session)

    with pytest.raises(HTTPException) as error:
        start_viewing_session(locked_lesson.id, db_session, student)
    assert error.value.status_code == 403
