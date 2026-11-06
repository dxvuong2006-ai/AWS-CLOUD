"""Endpoint thống kê khóa học cho giảng viên."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_instructor
from app.services import analytics_service

router = APIRouter(tags=["Analytics"])


@router.get("/instructor/courses/{course_id}/analytics")
def get_course_analytics(course_id: int, db: Session = Depends(get_db),
                         instructor=Depends(require_instructor)):
    """Trả thống kê của khóa học thuộc giảng viên."""
    result = analytics_service.get_course_analytics(db, course_id, instructor.id)
    if result is None:
        raise HTTPException(404, "Course not found.")
    return result
