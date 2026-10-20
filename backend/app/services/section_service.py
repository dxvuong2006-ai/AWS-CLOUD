from sqlalchemy.orm import Session

from app.models.section import Section
from app.repositories import courses_repo, sections_repo


class CourseNotFoundError(Exception):
    pass


class CourseOwnershipError(Exception):
    pass

# tạo section
def create_section(
    db: Session, *, course_id: int, instructor_id: int, title: str, position: int
) -> Section:
    course = courses_repo.get_course_by_id(db, course_id)
    if course is None:
        raise CourseNotFoundError("Course not found.")
    if course.instructor_id != instructor_id:
        raise CourseOwnershipError("You do not own this course.")
    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("Section title must not be blank.")
    return sections_repo.create(
        db, course_id=course_id, title=normalized_title, position=position
    )
