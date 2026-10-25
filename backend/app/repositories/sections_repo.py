from sqlalchemy.orm import Session

from app.models.section import Section

# lấy section bằng id
def get_by_id(db: Session, section_id: int) -> Section | None:
    return db.query(Section).filter(Section.id == section_id).first()

# tạo section mới
def create(db: Session, *, course_id: int, title: str, position: int) -> Section:
    section = Section(course_id=course_id, title=title, position=position)
    try:
        db.add(section)
        db.commit()
        db.refresh(section)
        return section
    except Exception:
        db.rollback()
        raise

# danh sách section theo 1 khóa học
def list_by_course(db: Session, course_id: int) -> list[Section]:
    return (
        db.query(Section)
        .filter(Section.course_id == course_id)
        .order_by(Section.position.asc(), Section.id.asc())
        .all()
    )