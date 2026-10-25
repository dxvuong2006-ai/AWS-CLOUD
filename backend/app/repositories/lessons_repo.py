from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.section import Section

# lấy lesson theo id
def get_by_id(db: Session, lesson_id: int) -> Lesson | None:
    return db.query(Lesson).filter(Lesson.id == lesson_id).first()

# lấy danh sách lesson của 1 section
def get_by_section(
    db: Session, section_id: int, *, skip: int = 0, limit: int = 100
) -> list[Lesson]:
    return (
        db.query(Lesson)
        .filter(Lesson.section_id == section_id)
        .order_by(Lesson.position.asc(), Lesson.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

# lấy section
def get_section(db: Session, section_id: int) -> Section | None:
    return db.query(Section).filter(Section.id == section_id).first()

# lấy course
def get_course(db: Session, course_id: int) -> Course | None:
    return db.query(Course).filter(Course.id == course_id).first()


def has_enrollment(db: Session, *, student_id: int, course_id: int) -> bool:
    return (
        db.query(Enrollment.id)
        .filter(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
        )
        .first()
        is not None
    )


def create(
    db: Session, *, section_id: int, title: str, position: int = 1
) -> Lesson:
    lesson = Lesson(
        section_id=section_id,
        title=title,
        position=position,
        status="DRAFT",
    )
    try:
        db.add(lesson)
        db.commit()
        db.refresh(lesson)
        return lesson
    except Exception:
        db.rollback()
        raise


def update(db: Session, lesson: Lesson, changes: dict) -> Lesson:
    allowed = {"title", "position"}
    for field, value in changes.items():
        if field in allowed:
            setattr(lesson, field, value)
    try:
        db.commit()
        db.refresh(lesson)
        return lesson
    except Exception:
        db.rollback()
        raise


def delete(db: Session, lesson: Lesson) -> None:
    try:
        db.delete(lesson)
        db.commit()
    except Exception:
        db.rollback()
        raise
