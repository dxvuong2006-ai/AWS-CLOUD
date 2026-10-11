from sqlalchemy.orm import Session

from app.models.course import Course


def get_published_courses(db: Session) -> list[Course]:
    return (
        db.query(Course)
        .filter(Course.status == "PUBLISHED")
        .order_by(Course.id.desc())
        .all()
    )


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