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


def get_section_by_id(db: Session, section_id: int) -> Section | None:
    """Giữ tên truy vấn chương học tương thích với module Quiz/Unlock."""
    return get_by_id(db, section_id)


def list_sections_by_course(db: Session, course_id: int) -> list[Section]:
    """Giữ tên truy vấn danh sách chương của phiên bản Người C."""
    return list_by_course(db, course_id)
