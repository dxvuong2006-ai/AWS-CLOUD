#HTTP Router tiếp nhận request Quiz & Unlock
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_student
from app.models.user import User
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.schemas.quiz import (
    QuizAttemptResultResponse,
    QuizDetailResponse,
    QuizHistoryItemResponse,
    QuizSubmitRequest,
)
from app.services import quiz_service, unlock_service

router = APIRouter(tags=["Quizzes"])


@router.get(
    "/sections/{section_id}/quiz",
    response_model=QuizDetailResponse,
    responses={
        403: {"description": "Section is locked or quiz is not approved."},
        404: {"description": "Section or quiz was not found."},
    },
)
def get_section_quiz(
    section_id: int,
    lesson_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    return quiz_service.get_checkpoint(
        db,
        section_id=section_id,
        student_id=current_user.id,
        lesson_id=lesson_id,
    )


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=QuizAttemptResultResponse,
    status_code=200,
    responses={
        403: {"description": "Section is locked or quiz is not approved."},
        404: {"description": "Quiz or its section was not found."},
        409: {"description": "Request ID was reused with different content."},
        422: {"description": "Quiz submission is invalid."},
    },
)
def submit_quiz(
    quiz_id: int,
    body: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    return quiz_service.submit_attempt(
        db,
        quiz_id=quiz_id,
        student_id=current_user.id,
        payload=body,
    )


@router.get(
    "/quizzes/{quiz_id}/attempts",
    response_model=list[QuizAttemptResultResponse],
)
def get_quiz_attempt_history(
    quiz_id: int,
    limit: int = Query(default=20, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    return quiz_service.attempt_history(
        db,
        quiz_id=quiz_id,
        student_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/student/quizzes/history",
    response_model=list[QuizHistoryItemResponse],
)
def get_student_quiz_history(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    """Trả lịch sử thi có phân trang của học viên hiện tại.

    Args:
        skip: Số lượt thi bỏ qua khi phân trang.
        limit: Số lượt thi tối đa cần lấy.
        db: Session SQLAlchemy được bên gọi cung cấp.
        current_user: Học viên được dependency xác định cho yêu cầu hiện
            tại.

    Returns:
        Danh sách dữ liệu theo QuizHistoryItemResponse.
    """
    return quiz_service.get_student_quiz_history(
        db,
        student_id=current_user.id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/courses/{course_id}/unlock-status",
    response_model=list[dict],
)
def get_course_unlock_status(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    """Trả trạng thái mở khóa của học viên trong khóa học.

    Args:
        course_id: Mã khóa học chứa các chương cần kiểm tra.
        db: Session SQLAlchemy được bên gọi cung cấp.
        current_user: Học viên được dependency xác định cho yêu cầu hiện
            tại.

    Returns:
        Danh sách section_id/is_unlocked của các chương trong khóa học.
    """
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Course not found.")
    if course.status != "PUBLISHED":
        raise HTTPException(403, "Course is not published.")
    if db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == current_user.id,
        )
    ) is None:
        raise HTTPException(403, "Course enrollment is required.")
    return unlock_service.get_course_unlock_status(
        db,
        student_id=current_user.id,
        course_id=course_id,
    )
