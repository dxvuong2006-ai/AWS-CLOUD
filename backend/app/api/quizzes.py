from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_student
from app.models.user import User
from app.schemas.quiz import QuizAttemptResultResponse, QuizAttemptSubmitRequest, QuizDetailResponse
from app.services import quiz_service

router = APIRouter(tags=["Checkpoints"])


@router.get("/sections/{section_id}/quiz", response_model=QuizDetailResponse)
def get_checkpoint(section_id: int, lesson_id: int | None = Query(default=None, gt=0),
                   db: Session = Depends(get_db), student: User = Depends(require_student)):
    return quiz_service.get_checkpoint(db, section_id, student.id, lesson_id)


@router.post("/quizzes/{quiz_id}/attempts", response_model=QuizAttemptResultResponse)
def submit_attempt(quiz_id: int, payload: QuizAttemptSubmitRequest,
                   db: Session = Depends(get_db), student: User = Depends(require_student)):
    return quiz_service.submit_attempt(db, quiz_id, student.id, payload)


@router.get("/quizzes/{quiz_id}/attempts", response_model=list[QuizAttemptResultResponse])
def history(quiz_id: int, limit: int = Query(default=20, ge=1, le=100),
            offset: int = Query(default=0, ge=0), db: Session = Depends(get_db),
            student: User = Depends(require_student)):
    return quiz_service.attempt_history(db, quiz_id, student.id, limit, offset)
