from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_instructor
from app.schemas.lesson import LessonApprovalResponse
from app.services import review_service

router = APIRouter(tags=["Review"])


@router.post(
    "/lessons/{lesson_id}/approve", response_model=LessonApprovalResponse,
    responses={
        401: {"description": "Invalid user identity."}, 403: {"description": "Owning instructor required."},
        404: {"description": "Lesson not found."}, 409: {"description": "Not reviewable, incomplete content, or concurrent operation."},
        502: {"description": "Processed video storage unavailable."}, 503: {"description": "Approval migration not applied."},
    },
)
def approve_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    instructor=Depends(require_instructor),
):
    return review_service.approve_lesson(db, lesson_id, instructor_id=instructor.id)
