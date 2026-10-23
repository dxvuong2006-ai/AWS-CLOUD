from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_student
from app.models.section import Section
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
from app.services.unlock_service import SectionLockedError

router = APIRouter(tags=["Quizzes"])


@router.get(
    "/sections/{section_id}/quiz",
    response_model=QuizDetailResponse,
)
def get_section_quiz(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    try:
        section = db.query(Section).filter(Section.id == section_id).first()
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
