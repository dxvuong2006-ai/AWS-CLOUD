import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_student
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.section import Section
from app.models.viewing_session import ViewingSession
from app.models.progress_update import ProgressUpdate
from app.schemas.learning import ProgressUpdateRequest
from app.services import lesson_service
from app.services.unlock_service import SectionLockedError

router = APIRouter(tags=["Learning progress"])


def _is_lesson_completed(duration_seconds, watched_seconds: float) -> bool:
    return bool(
        duration_seconds
        and duration_seconds > 0
        and watched_seconds >= duration_seconds * 0.1
    )


def _assert_student_lesson_access(db: Session, lesson_id: int, student) -> None:
    try:
        lesson_service.get_lesson_for_user(
            db, lesson_id, user_id=student.id, user_role=student.role
        )
    except (
        lesson_service.PublishedCourseRequiredError,
        lesson_service.LessonAccessDeniedError,
        SectionLockedError,
    ) as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/lessons/{lesson_id}/viewing-sessions")
def start_viewing_session(
    lesson_id: int,
    db: Session = Depends(get_db),
    student=Depends(require_student),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found.")
    _assert_student_lesson_access(db, lesson_id, student)
    section = db.get(Section, lesson.section_id)
    course = db.get(Course, section.course_id) if section else None
    if course is None or not db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course.id,
            Enrollment.student_id == student.id,
        )
    ):
        raise HTTPException(403, "You are not enrolled in this course.")
    viewing_session = ViewingSession(
        id=str(uuid.uuid4()), student_id=student.id, lesson_id=lesson_id
    )
    db.add(viewing_session)
    db.commit()
    return {"id": viewing_session.id}


@router.put("/lessons/{lesson_id}/progress", response_model=dict)
def save_lesson_progress(
    lesson_id: int,
    payload: ProgressUpdateRequest,
    db: Session = Depends(get_db),
    student=Depends(require_student),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found.")
    _assert_student_lesson_access(db, lesson_id, student)
    section = db.get(Section, lesson.section_id)
    course = db.get(Course, section.course_id) if section else None
    if course is None or not db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course.id,
            Enrollment.student_id == student.id,
        )
    ):
        raise HTTPException(403, "You are not enrolled in this course.")

    session = db.scalar(
        select(ViewingSession)
        .where(ViewingSession.id == str(payload.playback_session_id))
        .with_for_update()
    )
    if session is None or session.student_id != student.id or session.lesson_id != lesson_id:
        raise HTTPException(403, "Invalid viewing session.")

    progress = db.scalar(
        select(LessonProgress).where(
            LessonProgress.student_id == student.id,
            LessonProgress.lesson_id == lesson_id,
        )
    )
    previous_update = db.get(ProgressUpdate, str(payload.request_id))
    if previous_update is not None:
        if (
            previous_update.student_id != student.id
            or previous_update.lesson_id != lesson_id
        ):
            raise HTTPException(409, "Request id was already used.")
        return previous_update.response
    if payload.sequence <= session.last_sequence:
        raise HTTPException(409, "Progress sequence is stale.")

    merged = []
    prior_ranges = progress.watched_ranges if progress is not None else []
    for start, end in sorted(
        [*prior_ranges, *payload.watched_ranges],
        key=lambda r: (r[0], r[1])
    ):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    watched_seconds = sum(end - start for start, end in merged)

    if progress is None:
        progress = LessonProgress(student_id=student.id, lesson_id=lesson_id)
        db.add(progress)

    progress.watched_seconds = int(watched_seconds)
    progress.last_position_seconds = payload.last_position_seconds
    progress.watched_ranges = [list(item) for item in merged]
    progress.playback_session_id = str(payload.playback_session_id)
    progress.last_sequence = payload.sequence
    progress.last_request_id = str(payload.request_id)
    session.last_sequence = payload.sequence
    progress.completed = _is_lesson_completed(lesson.duration_seconds, watched_seconds)
    response = _progress_response(progress)
    db.add(
        ProgressUpdate(
            request_id=str(payload.request_id),
            student_id=student.id,
            lesson_id=lesson_id,
            response=response,
        )
    )
    db.commit()
    db.refresh(progress)
    return response


def _progress_response(progress: LessonProgress) -> dict:
    return {
        "last_position_seconds": progress.last_position_seconds,
        "watched_seconds": progress.watched_seconds,
        "watched_ranges": progress.watched_ranges or [],
        "completed": progress.completed,
    }


@router.get("/courses/{course_id}/progress")
def get_course_progress(
    course_id: int,
    db: Session = Depends(get_db),
    student=Depends(require_student),
):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Course not found.")
    if not db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == student.id,
        )
    ):
        raise HTTPException(403, "You are not enrolled in this course.")
    lessons = db.scalars(
        select(Lesson)
        .join(Section, Section.id == Lesson.section_id)
        .where(Section.course_id == course_id, Lesson.status == "PUBLISHED")
        .order_by(Section.position.asc(), Lesson.position.asc(), Lesson.id.asc())
    ).all()
    rows = []
    completed_count = 0
    for lesson in lessons:
        progress = db.scalar(
            select(LessonProgress).where(
                LessonProgress.student_id == student.id,
                LessonProgress.lesson_id == lesson.id,
            )
        )
        watched = progress.watched_seconds if progress else 0
        duration = lesson.duration_seconds or 0
        percent = min(100.0, watched * 100 / duration) if duration > 0 else 0.0
        completed = _is_lesson_completed(lesson.duration_seconds, watched)
        if completed:
            completed_count += 1
        rows.append({
            "lesson_id": lesson.id,
            "progress_percent": round(percent, 2),
            "completed": completed,
            "last_position_seconds": progress.last_position_seconds if progress else 0,
            "watched_seconds": watched,
            "watched_ranges": progress.watched_ranges if progress else [],
        })
    overall = completed_count * 100 / len(lessons) if lessons else 0.0
    return {
        "course_id": course_id,
        "completion_threshold_percent": 10,
        "overall_percent": round(overall, 2),
        "lessons": rows,
    }
