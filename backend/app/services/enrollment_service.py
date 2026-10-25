
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.repositories import courses_repo, enrollments_repo


class CourseNotFoundError(Exception):
    pass


class CourseNotPublishedError(Exception):
    pass


class AlreadyEnrolledError(Exception):
    pass

# đăng ký khóa học
def enroll_course(
    db: Session,
    student_id: int,
    course_id: int,
) -> Enrollment:
    # Kiểm tra khóa học tồn tại
    course = courses_repo.get_course_by_id(db, course_id)

    if course is None:
        raise CourseNotFoundError()

    # Chỉ cho đăng ký khóa học đã xuất bản
    course_status = getattr(course.status, "value", course.status)

    if str(course_status).upper() != "PUBLISHED":
        raise CourseNotPublishedError()

    # Kiểm tra sinh viên đã đăng ký chưa
    existing = enrollments_repo.get_enrollment(
        db=db,
        student_id=student_id,
        course_id=course_id,
    )

    if existing is not None:
        raise AlreadyEnrolledError()

    # Tạo đăng ký
    try:
        return enrollments_repo.create_enrollment(
            db=db,
            student_id=student_id,
            course_id=course_id,
        )
    except IntegrityError as exc:
        # Có thể một request khác vừa đăng ký cùng lúc.
        raise AlreadyEnrolledError() from exc
