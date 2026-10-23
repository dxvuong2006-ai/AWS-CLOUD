from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_student
from app.models.user import User
from app.repositories import sections_repo
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
from app.services.unlock_service import SectionLockedError

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
    try:
        section = sections_repo.get_section_by_id(db, section_id)
        if section is None:
            raise HTTPException(status_code=404, detail="Section not found.")

        unlock_service.assert_section_unlocked(
            db,
            student_id=current_user.id,
            course_id=section.course_id,
            section_id=section_id,
        )
        return quiz_service.get_quiz_for_student(
            db,
            section_id=section_id,
        )
    except (SectionLockedError, QuizNotApprovedError, QuizAccessDeniedError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except QuizNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=QuizAttemptResponse,
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
    return unlock_service.get_course_unlock_status(
        db,
        student_id=current_user.id,
        course_id=course_id,
    )
