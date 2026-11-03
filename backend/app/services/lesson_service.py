from sqlalchemy.orm import Session

from app.models.lesson import Lesson
from app.repositories import lessons_repo, review_repo


class LessonNotFoundError(Exception):
    pass


class SectionNotFoundError(Exception):
    pass


class CourseNotFoundError(Exception):
    pass


class CourseOwnershipError(Exception):
    pass


class PublishedCourseRequiredError(Exception):
    pass


class LessonAccessDeniedError(Exception):
    pass

# lấy section và course của 1 lesson
def _get_section_and_course(db: Session, section_id: int):
    section = lessons_repo.get_section(db, section_id)
    if section is None:
        raise SectionNotFoundError("Section not found.")

    course = lessons_repo.get_course(db, section.course_id)
    if course is None:
        raise CourseNotFoundError("Course not found.")

    return section, course

# tạo lesson
def create_lesson(
    db: Session,
    *,
    section_id: int,
    instructor_id: int,
    title: str,
    position: int = 1,
) -> Lesson:
    _, course = _get_section_and_course(db, section_id)

    if course.instructor_id != instructor_id:
        raise CourseOwnershipError("You do not own this course.")

    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("Lesson title must not be blank.")

    return lessons_repo.create(
        db,
        section_id=section_id,
        title=normalized_title,
        position=position,
    )

# kiểm tra quyền truy cập lesson
def _check_lesson_access(db: Session, course, user_id: int, user_role: str) -> None:
    role = user_role.upper()
    if role == "INSTRUCTOR":
        if course.instructor_id != user_id:
            raise CourseOwnershipError("You do not own this course.")
        return

    if role != "STUDENT":
        raise LessonAccessDeniedError("You do not have access to this lesson.")

    if str(course.status).upper() != "PUBLISHED":
        raise PublishedCourseRequiredError("Lesson is not available.")
    if not lessons_repo.has_enrollment(
        db, student_id=user_id, course_id=course.id
    ):
        raise LessonAccessDeniedError("You are not enrolled in this course.")

# lấy lesson cho người dùng
def get_lesson_for_user(
    db: Session, lesson_id: int, *, user_id: int, user_role: str
) -> Lesson:
    lesson = lessons_repo.get_by_id(db, lesson_id)
    if lesson is None:
        raise LessonNotFoundError("Lesson not found.")

    _, course = _get_section_and_course(db, lesson.section_id)
    _check_lesson_access(db, course, user_id, user_role)

    if user_role.upper() == "STUDENT" and lesson.status not in (
        "APPROVED", "PUBLISHED",
    ):
        raise LessonAccessDeniedError("Lesson is awaiting instructor approval.")
    return lesson

# cập nhật lesson
def update_lesson(
    db: Session, *, lesson_id: int, instructor_id: int, changes: dict
) -> Lesson:
    lesson = lessons_repo.get_by_id(db, lesson_id)
    if lesson is None:
        raise LessonNotFoundError("Lesson not found.")

    _, course = _get_section_and_course(db, lesson.section_id)
    if course.instructor_id != instructor_id:
        raise CourseOwnershipError("You do not own this course.")

    safe_changes = {
        key: value
        for key, value in changes.items()
        if key in {"title", "position"} and value is not None
    }
    if "title" in safe_changes:
        safe_changes["title"] = safe_changes["title"].strip()
        if not safe_changes["title"]:
            raise ValueError("Lesson title must not be blank.")

    return lessons_repo.update(db, lesson, safe_changes)

# lấy danh sách lessons của 1 section
def list_lessons_for_section(
    db: Session,
    section_id: int,
    *,
    user_id: int,
    user_role: str,
    skip: int = 0,
    limit: int = 100,
) -> list[Lesson]:
    _, course = _get_section_and_course(db, section_id)
    _check_lesson_access(db, course, user_id, user_role)
    if user_role.upper() == "STUDENT":
        return review_repo.list_visible_lessons(
            db, section_id, skip=skip, limit=limit,
        )
    return lessons_repo.get_by_section(db, section_id, skip=skip, limit=limit)
