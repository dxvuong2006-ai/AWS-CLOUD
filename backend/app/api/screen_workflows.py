"""Endpoints connecting UI screens 21–35 to owner-scoped services."""
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_student, require_instructor, get_current_user
from app.services import screen_workflows as service, remediation_service as remediation

router = APIRouter(tags=["Screen workflows"])

class Start(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attempt_id: int = Field(gt=0)
    regenerate: bool = False

class Advance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["explanation", "card"]
    item_id: str = Field(min_length=1, max_length=100)

class Answers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[str] = Field(min_length=2, max_length=3)

@router.get("/instructor/courses")
def courses(db: Session = Depends(get_db), user=Depends(require_instructor)):
    return service.instructor_courses(db, user.id)

@router.get("/instructor/courses/{course_id}")
def course(course_id: int, db: Session = Depends(get_db), user=Depends(require_instructor)):
    return service.course_detail(db, service.owned_course(db, user.id, course_id))

@router.get("/instructor/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(require_instructor)):
    return service.dashboard(db, user.id)

@router.get("/instructor/review-queue")
def queue(db: Session = Depends(get_db), user=Depends(require_instructor)):
    return service.queue(db, user.id)

@router.get("/instructor/students")
def students(course_id: int | None = Query(None, gt=0),
             db: Session = Depends(get_db), user=Depends(require_instructor)):
    return service.instructor_students(db, user.id, course_id)

@router.get("/instructor/students/{student_id}")
def student(student_id: int, db: Session = Depends(get_db),
            user=Depends(require_instructor)):
    return service.instructor_student(db, user.id, student_id)

@router.get("/students/me/checkpoint-history")
def history(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user=Depends(require_student)):
    return service.history(db, user.id, offset, limit)

@router.get("/courses/{course_id}/completion")
def completion(course_id: int, db: Session = Depends(get_db), user=Depends(require_student)):
    return service.completion(db, user.id, course_id)

@router.post("/student/remediation")
def start(payload: Start, db: Session = Depends(get_db), user=Depends(require_student)):
    return remediation.start(db, user.id, payload.attempt_id, payload.regenerate)

@router.get("/student/remediation/{session_id}")
def session(session_id: int, db: Session = Depends(get_db), user=Depends(require_student)):
    return remediation.public(db, remediation.owned(db, user.id, session_id))

@router.post("/student/remediation/{session_id}/advance")
def advance(session_id: int, payload: Advance, db: Session = Depends(get_db), user=Depends(require_student)):
    return remediation.advance(db, user.id, session_id, payload.kind, payload.item_id)

@router.post("/student/remediation/{session_id}/practice")
def practice(session_id: int, payload: Answers, db: Session = Depends(get_db), user=Depends(require_student)):
    return remediation.submit(db, user.id, session_id, payload.answers)


@router.get("/students/me/learning-overview")
def overview(db: Session = Depends(get_db), user=Depends(require_student)):
    return service.overview(db, user.id)


@router.get("/lessons/{lesson_id}/content")
def content(lesson_id: int, db: Session = Depends(get_db),
            user=Depends(get_current_user)):
    from app.services import lesson_service
    from app.api.lessons import _raise_service_error
    from app.models.section import Section
    try:
        lesson = lesson_service.get_lesson_for_user(db, lesson_id, user_id=user.id, user_role=user.role)
    except Exception as exc:
        _raise_service_error(exc)
    section = db.get(Section, lesson.section_id)
    transcript = lesson.transcript_json
    segments = transcript.get("segments", []) if isinstance(transcript, dict) else []
    return {"id": lesson.id, "title": lesson.title, "course_id": section.course_id,
        "section_id": section.id, "publication_status": lesson.status,
        "processing_status": "READY" if lesson.status == "PUBLISHED" else lesson.status,
        "summary": lesson.summary, "key_concepts": lesson.key_concepts_json,
        "transcript": segments}
