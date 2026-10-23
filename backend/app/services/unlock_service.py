from sqlalchemy.orm import Session

from app.models.section import Section
from app.repositories import quizzes_repo
from app.repositories import sections_repo


class SectionLockedError(Exception):
    pass


class PrerequisiteQuizNotPassedError(Exception):
    pass


def _is_section_unlocked(
    db: Session,
    *,
    student_id: int,
    sections: list[Section],
    section_id: int,
) -> bool:
    section_index = next(
        (index for index, section in enumerate(sections) if section.id == section_id),
        None,
    )
    if section_index is None:
        return False
    if section_index == 0:
        return True

    for previous_section in sections[:section_index]:
        previous_quiz = quizzes_repo.get_quiz_by_section(db, previous_section.id)
        if previous_quiz is not None and not quizzes_repo.has_passed_quiz(
            db,
            student_id=student_id,
            quiz_id=previous_quiz.id,
        ):
            return False
    return True


def is_section_unlocked(
    db: Session,
    *,
    student_id: int,
    course_id: int,
    section_id: int,
) -> bool:
    sections = sections_repo.list_sections_by_course(db, course_id)
    return _is_section_unlocked(
        db,
        student_id=student_id,
        sections=sections,
        section_id=section_id,
    )


def assert_section_unlocked(
    db: Session,
    *,
    student_id: int,
    course_id: int,
    section_id: int,
) -> None:
    if not is_section_unlocked(
        db,
        student_id=student_id,
        course_id=course_id,
        section_id=section_id,
    ):
        raise SectionLockedError(
            "Previous section requirements must be met to unlock this section."
        )


def get_course_unlock_status(
    db: Session,
    *,
    student_id: int,
    course_id: int,
) -> list[dict]:
    sections = sections_repo.list_sections_by_course(db, course_id)
    status = []
    is_unlocked = True
    for section in sections:
        status.append(
            {
                "section_id": section.id,
                "is_unlocked": is_unlocked,
            }
        )
        previous_quiz = quizzes_repo.get_quiz_by_section(db, section.id)
        if previous_quiz is not None and not quizzes_repo.has_passed_quiz(
            db,
            student_id=student_id,
            quiz_id=previous_quiz.id,
        ):
            is_unlocked = False
    return status
