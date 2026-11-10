
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment


def list_student_enrollments(
    db: Session,
    student_id: int,
) -> list[Enrollment]:
    statement = (
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
    )
    return list(db.scalars(statement).all())

# lấy enrollment
def get_enrollment(
    db: Session,
    student_id: int,
    course_id: int,
) -> Enrollment | None:
    statement = select(Enrollment).where(
        Enrollment.student_id == student_id,
        Enrollment.course_id == course_id,
    )
    return db.scalar(statement)

# tạo enrollment
def create_enrollment(
    db: Session,
    student_id: int,
    course_id: int,
) -> Enrollment:
    enrollment = Enrollment(
        student_id=student_id,
        course_id=course_id,
    )

    try:
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
