from sqlalchemy.orm import Session

from app.models.section import Section
from app.repositories import courses_repo, sections_repo


class CourseNotFoundError(Exception):
    pass


class CourseOwnershipError(Exception):
    pass


class CourseAccessDeniedError(Exception):
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

# danh sách section đối với mỗi khóa học (cái này dùng để hiển thị danh sách section khi vào trang của 1 course)
def list_sections_for_course(
    db: Session, *, course_id: int, user_id: int, user_role: str
) -> list[Section]:
    role = user_role.upper()
    if role not in {"STUDENT", "INSTRUCTOR"}:
        raise CourseAccessDeniedError("Student or Instructor role required.")

    course = courses_repo.get_course_by_id(db, course_id)
    if course is None:
        raise CourseNotFoundError("Course not found.")

    is_owner = role == "INSTRUCTOR" and course.instructor_id == user_id
    if not is_owner and str(course.status).upper() != "PUBLISHED":
        # Hide draft courses from non-owners.
        raise CourseNotFoundError("Course not found.")

    return sections_repo.list_by_course(db, course_id)