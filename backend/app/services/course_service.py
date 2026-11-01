from sqlalchemy.orm import Session

from app.repositories import courses_repo, lessons_repo, sections_repo
from app.schemas.course import CourseCreateRequest, CourseUpdateRequest

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