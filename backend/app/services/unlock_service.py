from sqlalchemy.orm import Session

from app.models.section import Section
from app.repositories import quizzes_repo


class SectionLockedError(Exception):
    pass


class PrerequisiteQuizNotPassedError(Exception):
    pass


def _get_course_sections(db: Session, course_id: int) -> list[Section]:
    return (
        db.query(Section)
        .filter(Section.course_id == course_id)
        .order_by(Section.position.asc())
        .all()
    )


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

    previous_section = sections[section_index - 1]
    previous_quiz = quizzes_repo.get_quiz_by_section(db, previous_section.id)
    if previous_quiz is None:
        return True

    return quizzes_repo.has_passed_quiz(
        db,
        student_id=student_id,
        quiz_id=previous_quiz.id,
    )


def is_section_unlocked(
    db: Session,
    *,
    student_id: int,
    course_id: int,
    section_id: int,
) -> bool:
    sections = _get_course_sections(db, course_id)
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
            "Previous section quiz must be passed with >= 80% to unlock this section."
        )


def get_course_unlock_status(
    db: Session,
    *,
    student_id: int,
    course_id: int,
) -> list[dict]:
    sections = _get_course_sections(db, course_id)
    return [
        {
            "section_id": section.id,
            "is_unlocked": _is_section_unlocked(
                db,
                student_id=student_id,
                sections=sections,
                section_id=section.id,
            ),
        }
        for section in sections
    ]
