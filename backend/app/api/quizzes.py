from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_student
from app.models.user import User
from app.schemas.quiz import (
    QuizAttemptResponse,
    QuizDetailResponse,
    QuizHistoryItemResponse,
    QuizSubmitRequest,
)
from app.services import quiz_service, unlock_service
from app.services.quiz_service import (
    InvalidSubmissionError,
    QuizAccessDeniedError,
    QuizNotApprovedError,
    QuizNotFoundError,
)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    """Trả đề thi đã duyệt sau khi kiểm tra mở khóa chương học.

    Args:
        section_id: Mã chương học cần xử lý.
        db: Session SQLAlchemy được bên gọi cung cấp.
        current_user: Học viên được dependency xác định cho yêu cầu hiện
            tại.

    Returns:
        Dữ liệu được lọc qua QuizDetailResponse, không gồm đáp án/lời giải.

    Raises:
        HTTPException: HTTP 403 khi bị khóa/chưa duyệt; 404 khi không có
            đề.
    """
    try:
        return quiz_service.get_unlocked_quiz_for_student(
            db,
            student_id=current_user.id,
            section_id=section_id,
        )
    except (QuizNotApprovedError, QuizAccessDeniedError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except QuizNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=QuizAttemptResponse,
    status_code=200,
    responses={
        400: {"description": "Quiz submission is invalid."},
        403: {"description": "Section is locked or quiz is not approved."},
        404: {"description": "Quiz or its section was not found."},
    },
)
def submit_quiz(
    quiz_id: int,
    body: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    """Tạo tài nguyên lượt thi từ câu trả lời của học viên.

    Kết quả được trả sau khi Service hoàn tất giao dịch nộp bài.

    Args:
        quiz_id: Mã bài trắc nghiệm cần xử lý.
        body: DTO chứa các câu trả lời của yêu cầu nộp bài.
        db: Session SQLAlchemy được bên gọi cung cấp.
        current_user: Học viên được dependency xác định cho yêu cầu hiện
            tại.

    Returns:
        QuizAttemptResponse với HTTP 200 và kết quả chấm bài.

    Raises:
        HTTPException: HTTP 400 cho bài nộp sai; 403 khi bị chặn; 404 nếu
            thiếu đề.
    """
    try:
        return quiz_service.submit_quiz(
            db,
            student_id=current_user.id,
            quiz_id=quiz_id,
            submission=body,
        )
    except (QuizNotApprovedError, QuizAccessDeniedError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except QuizNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidSubmissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    return unlock_service.get_course_unlock_status(
        db,
        student_id=current_user.id,
        course_id=course_id,
    )
