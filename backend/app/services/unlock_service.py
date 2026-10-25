from sqlalchemy.orm import Session

from app.repositories import quizzes_repo


class SectionLockedError(Exception):
    pass


class PrerequisiteQuizNotPassedError(Exception):
    pass


def is_section_unlocked(
    db: Session,
    *,
    student_id: int,
    course_id: int,
    section_id: int,
) -> bool:
    return any(
        item["section_id"] == section_id and item["is_unlocked"]
        for item in get_course_unlock_status(
            db,
            student_id=student_id,
            course_id=course_id,
        )
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
    progress = quizzes_repo.list_section_quiz_progress(
        db,
        student_id=student_id,
        course_id=course_id,
    )
    status = []
    is_unlocked = True
    for section_id, requirements_met in progress:
        status.append(
            {
                "section_id": section_id,
                "is_unlocked": is_unlocked,
            }
        )
        is_unlocked = is_unlocked and requirements_met
    return status
