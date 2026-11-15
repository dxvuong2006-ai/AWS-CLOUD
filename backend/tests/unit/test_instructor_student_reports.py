"""Regression coverage for owner-scoped instructor student progress reports."""

from datetime import datetime

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Quiz, QuizAttempt
from app.models.section import Section
from app.models.tutor import TutorSession
from app.models.user import User


def report_context(db_session, quiz_course):
    student, course, sections = quiz_course
    instructor = User(
        name="Course Owner", email="owner-report@example.test", role="INSTRUCTOR",
    )
    outsider = User(
        name="Other Instructor", email="other-report@example.test", role="INSTRUCTOR",
    )
    unenrolled = User(
        name="Unenrolled Student", email="unenrolled@example.test", role="STUDENT",
    )
    db_session.add_all([instructor, outsider, unenrolled])
    db_session.flush()
    course.instructor_id = instructor.id
    course.status = "PUBLISHED"
    lessons = [
        Lesson(section_id=sections[0].id, title=f"Published {position}",
               position=position, status="PUBLISHED")
        for position in (1, 2)
    ]
    db_session.add_all(lessons)
    db_session.add(Enrollment(student_id=student.id, course_id=course.id))
    db_session.commit()
    return instructor, outsider, unenrolled, student, course, lessons


def call_as(db_session, actor, method, path):
    def database_override():
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        with TestClient(app) as client:
            return getattr(client, method)(path)
    finally:
        app.dependency_overrides.clear()


def test_student_report_uses_completion_contract_for_progress_and_dashboard(
    db_session, quiz_course,
):
    owner, other_owner, _, student, course, lessons = report_context(
        db_session, quiz_course,
    )
    foreign_course = Course(
        instructor_id=other_owner.id, title="Other Instructor Course",
        status="PUBLISHED",
    )
    db_session.add(foreign_course)
    db_session.flush()
    foreign_section = Section(
        course_id=foreign_course.id, title="Other Section", position=1,
    )
    db_session.add(foreign_section)
    db_session.flush()
    owned_quiz = Quiz(section_id=lessons[0].section_id, title="Owned Quiz")
    foreign_quiz = Quiz(section_id=foreign_section.id, title="Foreign Quiz")
    db_session.add_all([owned_quiz, foreign_quiz])
    db_session.flush()
    db_session.add_all([
        Enrollment(student_id=student.id, course_id=foreign_course.id),
        QuizAttempt(
            student_id=student.id, quiz_id=owned_quiz.id, score=70,
            passed=False, attempt_number=1,
        ),
        QuizAttempt(
            student_id=student.id, quiz_id=foreign_quiz.id, score=100,
            passed=True, attempt_number=1,
        ),
    ])
    db_session.commit()

    detail = call_as(
        db_session, owner, "get", f"/instructor/students/{student.id}",
    )
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()
    assert set(detail_data) == {
        "id", "name", "email", "courses", "progress", "attempt_count",
        "passed_attempts", "pass_rate", "average_score", "last_score",
        "last_passed", "tutor_sessions", "weak_concepts",
    }
    assert detail_data["courses"] == [{
        "id": course.id, "title": course.title, "progress": 0,
        "attempt_count": 1, "passed_attempts": 0, "pass_rate": 0.0,
        "average_score": 70.0, "last_score": 70.0, "last_passed": False,
    }]
    assert detail_data["attempt_count"] == 1
    assert detail_data["average_score"] == 70.0
    assert detail_data["pass_rate"] == 0.0
    assert detail_data["last_score"] == 70.0
    assert detail_data["last_passed"] is False
    assert detail_data["tutor_sessions"] == 0

    # The list and dashboard routes use their own contracts; neither expects
    # progress_percent on the completion read model.
    listing = call_as(db_session, owner, "get", "/instructor/students")
    assert listing.status_code == 200, listing.text
    assert listing.json()[0]["progress"] == 0
    assert listing.json()[0]["last_score"] == 70.0
    assert listing.json()[0]["last_passed"] is False
    assert listing.json()[0]["pass_rate"] == 0.0
    dashboard = call_as(db_session, owner, "get", "/instructor/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["active_students"] == 1

    db_session.add(LessonProgress(
        student_id=student.id, lesson_id=lessons[0].id, watched_seconds=60,
        completed=True,
    ))
    db_session.commit()

    detail = call_as(
        db_session, owner, "get", f"/instructor/students/{student.id}",
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["courses"][0]["progress"] == 50
    assert detail.json()["progress"] == 50
    assert detail.json()["last_passed"] is False
    listing = call_as(db_session, owner, "get", "/instructor/students")
    assert listing.status_code == 200, listing.text
    assert listing.json()[0]["progress"] == 50
    assert listing.json()[0]["last_passed"] is False


def test_report_aggregates_multiple_owned_courses_and_scopes_tutor_sessions(
    db_session, quiz_course,
):
    owner, other_owner, _, student, first_course, first_lessons = report_context(
        db_session, quiz_course,
    )
    second_course = Course(
        instructor_id=owner.id, title="Second Owned Course", status="PUBLISHED",
    )
    foreign_course = Course(
        instructor_id=other_owner.id, title="Foreign Course", status="PUBLISHED",
    )
    db_session.add_all([second_course, foreign_course])
    db_session.flush()
    second_section = Section(course_id=second_course.id, title="Second", position=1)
    foreign_section = Section(course_id=foreign_course.id, title="Foreign", position=1)
    db_session.add_all([second_section, foreign_section])
    db_session.flush()
    second_lesson = Lesson(
        section_id=second_section.id, title="Second lesson", position=1,
        status="PUBLISHED",
    )
    foreign_lesson = Lesson(
        section_id=foreign_section.id, title="Foreign lesson", position=1,
        status="PUBLISHED",
    )
    db_session.add_all([second_lesson, foreign_lesson])
    db_session.flush()
    first_quiz = Quiz(
        section_id=first_lessons[0].section_id, title="First Checkpoint",
    )
    second_quiz = Quiz(section_id=second_section.id, title="Second Checkpoint")
    foreign_quiz = Quiz(section_id=foreign_section.id, title="Foreign Checkpoint")
    db_session.add_all([first_quiz, second_quiz, foreign_quiz])
    db_session.flush()
    db_session.add_all([
        Enrollment(student_id=student.id, course_id=second_course.id),
        Enrollment(student_id=student.id, course_id=foreign_course.id),
        QuizAttempt(
            student_id=student.id, quiz_id=first_quiz.id, score=70,
            passed=False, attempt_number=1, created_at=datetime(2026, 1, 1),
        ),
        QuizAttempt(
            student_id=student.id, quiz_id=second_quiz.id, score=90,
            passed=True, attempt_number=1, created_at=datetime(2026, 1, 2),
        ),
        QuizAttempt(
            student_id=student.id, quiz_id=foreign_quiz.id, score=100,
            passed=True, attempt_number=1, created_at=datetime(2026, 1, 3),
        ),
        TutorSession(student_id=student.id, lesson_id=first_lessons[0].id),
        TutorSession(student_id=student.id, lesson_id=second_lesson.id),
        TutorSession(student_id=student.id, lesson_id=foreign_lesson.id),
        LessonProgress(
            student_id=student.id, lesson_id=first_lessons[0].id,
            watched_seconds=60, completed=True,
        ),
    ])
    db_session.commit()

    detail = call_as(
        db_session, owner, "get", f"/instructor/students/{student.id}",
    )
    assert detail.status_code == 200, detail.text
    data = detail.json()
    assert data["progress"] == 33  # 1 of 3 published videos, independent of scores.
    assert data["attempt_count"] == 2
    assert data["passed_attempts"] == 1
    assert data["pass_rate"] == 50.0
    assert data["average_score"] == 80.0
    assert data["last_score"] == 90.0
    assert data["last_passed"] is True
    assert data["tutor_sessions"] == 2
    assert {row["title"] for row in data["courses"]} == {
        first_course.title, second_course.title,
    }
    assert {row["title"] for row in data["courses"]} != {
        first_course.title, second_course.title, foreign_course.title,
    }

    all_courses = call_as(db_session, owner, "get", "/instructor/students")
    assert all_courses.status_code == 200, all_courses.text
    row = all_courses.json()[0]
    assert row["progress"] == 33
    assert row["attempt_count"] == 2
    assert row["passed_attempts"] == 1
    assert row["pass_rate"] == 50.0
    assert row["last_score"] == 90.0

    first_only = call_as(
        db_session, owner, "get", f"/instructor/students?course_id={first_course.id}",
    )
    assert first_only.status_code == 200, first_only.text
    first_row = first_only.json()[0]
    assert first_row["attempt_count"] == 1
    assert first_row["passed_attempts"] == 0
    assert first_row["pass_rate"] == 0.0
    assert first_row["last_score"] == 70.0

    second_only = call_as(
        db_session, owner, "get", f"/instructor/students?course_id={second_course.id}",
    )
    assert second_only.status_code == 200, second_only.text
    second_row = second_only.json()[0]
    assert second_row["attempt_count"] == 1
    assert second_row["passed_attempts"] == 1
    assert second_row["pass_rate"] == 100.0
    assert second_row["last_score"] == 90.0


def test_report_returns_null_checkpoint_metrics_without_attempts(
    db_session, quiz_course,
):
    owner, _, _, _, course, _ = report_context(db_session, quiz_course)
    student = User(
        name="No Attempts", email="no-attempts@example.test", role="STUDENT",
    )
    db_session.add(student)
    db_session.flush()
    db_session.add(Enrollment(student_id=student.id, course_id=course.id))
    db_session.commit()

    detail = call_as(
        db_session, owner, "get", f"/instructor/students/{student.id}",
    )
    assert detail.status_code == 200, detail.text
    data = detail.json()
    assert data["attempt_count"] == 0
    assert data["average_score"] is None
    assert data["pass_rate"] is None
    assert data["last_score"] is None
    assert data["last_passed"] is None
    assert data["tutor_sessions"] == 0
    assert data["courses"][0]["average_score"] is None
    assert data["courses"][0]["pass_rate"] is None


def test_student_report_returns_not_found_without_owned_enrollment(
    db_session, quiz_course,
):
    owner, outsider, unenrolled, student, course, _ = report_context(
        db_session, quiz_course,
    )

    no_enrollment = call_as(
        db_session, owner, "get", f"/instructor/students/{unenrolled.id}",
    )
    assert no_enrollment.status_code == 404

    other_instructor = call_as(
        db_session, outsider, "get", f"/instructor/students/{student.id}",
    )
    assert other_instructor.status_code == 404

    unauthorized_course_filter = call_as(
        db_session, owner, "get",
        f"/instructor/students?course_id={course.id + 999}",
    )
    assert unauthorized_course_filter.status_code == 404


def test_student_report_rejects_non_instructor(db_session, quiz_course):
    _, _, _, student, _, _ = report_context(db_session, quiz_course)
    response = call_as(
        db_session, student, "get", f"/instructor/students/{student.id}",
    )
    assert response.status_code == 403
