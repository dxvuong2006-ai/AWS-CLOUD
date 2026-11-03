import pytest

from app.models.quiz import Quiz, QuizAttempt
from app.services import unlock_service
from app.services.unlock_service import SectionLockedError


def _create_quiz(db_session, section_id: int, *, approved: bool = True) -> Quiz:
    quiz = Quiz(
        section_id=section_id,
        title="Checkpoint",
        passing_score=80.0,
        is_approved=approved,
    )
    db_session.add(quiz)
    db_session.commit()
    return quiz


def test_unlock_requires_every_previous_section_quiz_passed(
    db_session,
    quiz_course,
):
    student, course, sections = quiz_course
    first_quiz = _create_quiz(db_session, sections[0].id)
    second_quiz = _create_quiz(db_session, sections[1].id)
    db_session.add(
        QuizAttempt(
            student_id=student.id,
            quiz_id=first_quiz.id,
            score=90,
            passed=True,
            attempt_number=1,
        )
    )
    db_session.commit()

    assert not unlock_service.is_section_unlocked(
        db_session,
        student_id=student.id,
        course_id=course.id,
        section_id=sections[2].id,
    )

    db_session.add(
        QuizAttempt(
            student_id=student.id,
            quiz_id=second_quiz.id,
            score=85,
            passed=True,
            attempt_number=1,
        )
    )
    db_session.commit()

    assert unlock_service.is_section_unlocked(
        db_session,
        student_id=student.id,
        course_id=course.id,
        section_id=sections[2].id,
    )


def test_unlock_preserves_no_quiz_and_unapproved_quiz_behavior(
    db_session,
    quiz_course,
):
    student, course, sections = quiz_course
    assert unlock_service.is_section_unlocked(
        db_session,
        student_id=student.id,
        course_id=course.id,
        section_id=sections[1].id,
    )

    unapproved_quiz = _create_quiz(
        db_session,
        sections[0].id,
        approved=False,
    )
    assert not unlock_service.is_section_unlocked(
        db_session,
        student_id=student.id,
        course_id=course.id,
        section_id=sections[1].id,
    )

    db_session.add(
        QuizAttempt(
            student_id=student.id,
            quiz_id=unapproved_quiz.id,
            score=100,
            passed=True,
            attempt_number=1,
        )
    )
    db_session.commit()
    assert unlock_service.is_section_unlocked(
        db_session,
        student_id=student.id,
        course_id=course.id,
        section_id=sections[1].id,
    )


def test_unlock_status_preserves_response_shape(db_session, quiz_course):
    student, course, sections = quiz_course
    status = unlock_service.get_course_unlock_status(
        db_session,
        student_id=student.id,
        course_id=course.id,
    )

    assert status == [
        {"section_id": sections[0].id, "is_unlocked": True},
        {"section_id": sections[1].id, "is_unlocked": True},
        {"section_id": sections[2].id, "is_unlocked": True},
    ]


def test_locked_section_error_uses_threshold_neutral_message(
    db_session,
    quiz_course,
):
    student, course, sections = quiz_course
    _create_quiz(db_session, sections[0].id)

    with pytest.raises(SectionLockedError) as error:
        unlock_service.assert_section_unlocked(
            db_session,
            student_id=student.id,
            course_id=course.id,
            section_id=sections[1].id,
        )

    assert str(error.value) == (
        "Previous section requirements must be met to unlock this section."
    )
    assert "80%" not in str(error.value)