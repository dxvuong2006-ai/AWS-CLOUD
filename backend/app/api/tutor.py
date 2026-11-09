"""Các endpoint Tutor dành cho học viên."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_student
from app.schemas.tutor import (
    PracticeSubmission, TutorMessageCreateRequest, TutorSessionCreateRequest,
    QuestionRemediationRequest,
)
from app.services import tutor_service

router = APIRouter(tags=["Tutor"])


def _call(operation, **kwargs):
    """Chuyển lỗi nghiệp vụ thành lỗi HTTP."""
    try:
        return operation(**kwargs)
    except tutor_service.TutorError as exc:
        raise HTTPException(exc.code, str(exc)) from exc


@router.post("/tutor/sessions", status_code=201)
def create_session(payload: TutorSessionCreateRequest,
                   db: Session = Depends(get_db),
                   student=Depends(require_student)):
    """Tạo phiên ôn tập từ lần thi của học viên."""
    return _call(tutor_service.create_session, db=db, student_id=student.id,
                 attempt_id=payload.attempt_id)


@router.post("/tutor/sessions/{session_id}/messages")
def send_message(session_id: int, payload: TutorMessageCreateRequest,
                 db: Session = Depends(get_db),
                 student=Depends(require_student)):
    """Gửi câu hỏi thuộc phạm vi bài giảng."""
    return _call(tutor_service.send_message, db=db, student_id=student.id,
                 session_id=session_id, message=payload.message)


@router.post("/tutor/sessions/{session_id}/practice-attempts")
def submit_practice(session_id: int, payload: PracticeSubmission,
                    db: Session = Depends(get_db),
                    student=Depends(require_student)):
    """Chấm các câu hỏi củng cố."""
    return _call(tutor_service.submit_practice, db=db, student_id=student.id,
                 session_id=session_id, answers=payload.answers)



@router.post("/tutor/remediations")
def remediate_question(payload: QuestionRemediationRequest,
                       db: Session = Depends(get_db),
                       student=Depends(require_student)):
    """Ôn tập một câu học viên đã nộp sai."""
    return _call(tutor_service.remediate_question, db=db,
                 student_id=student.id, payload=payload)
