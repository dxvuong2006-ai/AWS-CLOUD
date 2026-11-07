from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.repositories import courses_repo, lessons_repo, sections_repo
from app.schemas.course import CourseCreateRequest, CourseUpdateRequest
from app.utils.errors import ConflictError, ForbiddenError, NotFoundError
from app.lesson_states import LessonStatus
from app.services.review_service import validate_review_content

# Tạo khóa học mới
def create_course(
    db: Session,
    instructor_id: int,
    data: CourseCreateRequest,
):
    course_data = data.model_dump()

    # Khóa học mới mặc định ở trạng thái nháp
    course_data["status"] = "DRAFT"
    course_data["instructor_id"] = instructor_id

    return courses_repo.create_course(db, course_data)

# lấy danh sách courses được publish
def get_courses(db: Session):
    return courses_repo.get_published_courses(db)

# lấy chi tiết của 1 khóa học (course)
def get_course_detail(db: Session, course_id: int):
    course = courses_repo.get_published_course_by_id(db, course_id)
    if course is None:
        return None

    sections = sections_repo.list_by_course(db, course_id)
    course_data = {
        column.name: getattr(course, column.name)
        for column in course.__table__.columns
    }
    course_data["sections"] = [
        {
            "id": section.id,
            "course_id": section.course_id,
            "title": section.title,
            "position": section.position,
            "lessons": lessons_repo.get_by_section(db, section.id),
        }
        for section in sections
    ]
    return course_data

# Cập nhật khóa học
def update_course(
    db: Session,
    course_id: int,
    instructor_id: int,
    data: CourseUpdateRequest,
):
    # Chỉ lấy những trường client thực sự gửi lên
    update_data = data.model_dump(exclude_unset=True)

    if not update_data:
        return courses_repo.get_course_by_id_and_instructor(
            db, course_id, instructor_id
        )

    # Không cho phép sửa các trường ngoài phạm vi cập nhật
    allowed_fields = {
        "title",
        "description",
        "learning_objectives",
    }
    update_data = {
        key: value
        for key, value in update_data.items()
        if key in allowed_fields
    }

    return courses_repo.update_course(
        db=db,
        course_id=course_id,
        instructor_id=instructor_id,
        update_data=update_data,
    )


def publish_course(db: Session, course_id: int, *, instructor_id: int):
    try:
        course = courses_repo.lock_by_id(db, course_id)
        if course is None:
            raise NotFoundError("Course not found.")
        if course.instructor_id != instructor_id:
            raise ForbiddenError("You do not own this course.")
        if course.status == "PUBLISHED":
            db.commit()
            return course
        if course.status != "DRAFT":
            raise ConflictError("Course is not in a publishable state.", code="INVALID_COURSE_STATUS")
        sections = courses_repo.lock_sections(db, course.id)
        lessons = lessons_repo.lock_by_course(db, course.id)
        if not sections or not lessons or any(not any(l.section_id == s.id for l in lessons) for s in sections):
            raise ConflictError("Every course section must contain a lesson.", code="COURSE_CONTENT_REQUIRED")
        # Approving a review publishes the lesson directly. Do not use upload,
        # processing, or legacy data as a substitute for explicit review approval.
        if any(lesson.status != LessonStatus.PUBLISHED.value for lesson in lessons):
            raise ConflictError("Every lesson must be explicitly approved before publishing.", code="LESSON_APPROVAL_REQUIRED")
        for lesson in lessons:
            validate_review_content(lesson)
        courses_repo.mark_published(db, course, lessons)
        db.commit()
        return course
    except OperationalError as exc:
        db.rollback()
        if getattr(exc.orig, "pgcode", None) == "55P03":
            raise ConflictError("Another operation is updating this course.", code="COURSE_BUSY") from None
        raise
    except Exception:
        db.rollback()
        raise
