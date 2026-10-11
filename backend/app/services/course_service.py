from sqlalchemy.orm import Session

from app.repositories import courses_repo


def get_courses(db: Session):
    return courses_repo.get_published_courses(db)


def get_course_detail(db: Session, course_id: int):
    return courses_repo.get_published_course_by_id(db, course_id)