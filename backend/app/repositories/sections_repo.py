from sqlalchemy.orm import Session

from app.models.section import Section


def get_section_by_id(db: Session, section_id: int) -> Section | None:
    return db.query(Section).filter(Section.id == section_id).first()


def list_sections_by_course(db: Session, course_id: int) -> list[Section]:
    return (
        db.query(Section)
        .filter(Section.course_id == course_id)
        .order_by(Section.position.asc())
        .all()
    )
