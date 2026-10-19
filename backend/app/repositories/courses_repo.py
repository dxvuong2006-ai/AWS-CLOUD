from sqlalchemy.orm import Session

from app.models.course import Course

# Tạo khóa học mới
def create_course(
    db: Session,
    course_data: dict,
) -> Course:
    course = Course(**course_data)

    db.add(course)
    db.commit()
    db.refresh(course)

    return course

# Lấy danh sách khóa học đã publish
def get_published_courses(db: Session) -> list[Course]:
    return (
        db.query(Course)
        .filter(Course.status == "PUBLISHED")
        .order_by(Course.id.desc())
        .all()
    )

# Lấy chi tiết khóa học đã publish
def get_published_course_by_id(
    db: Session,
    course_id: int,
) -> Course | None:
    return (
        db.query(Course)
        .filter(
            Course.id == course_id,
            Course.status == "PUBLISHED",
        )
        .first()
    )

# Lấy khóa học thuộc một giảng viên
def get_course_by_id_and_instructor(
    db: Session,
    course_id: int,
    instructor_id: int,
) -> Course | None:
    return (
        db.query(Course)
        .filter(
            Course.id == course_id,
            Course.instructor_id == instructor_id,
        )
        .first()
    )


# Cập nhật khóa học thuộc một giảng viên
def update_course(
    db: Session,
    course_id: int,
    instructor_id: int,
    update_data: dict,
) -> Course | None:
    course = get_course_by_id_and_instructor(
        db,
        course_id,
        instructor_id,
    )

    if course is None:
        return None

    for key, value in update_data.items():
        setattr(course, key, value)

    db.commit()
    db.refresh(course)

    return course