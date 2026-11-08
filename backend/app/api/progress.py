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
from app.schemas.learning import WatchedRangesRequest

router = APIRouter(tags=["Learning progress"])


@router.post("/lessons/{lesson_id}/viewing-sessions")
def start_viewing_session(
    lesson_id: int,
    db: Session = Depends(get_db),
    student=Depends(require_student),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found.")
    section = db.get(Section, lesson.section_id)
    course = db.get(Course, section.course_id) if section else None
    if course is None or not db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course.id,
            Enrollment.student_id == student.id,
        )
    ):
        raise HTTPException(403, "You are not enrolled in this course.")
    return {"id": str(uuid.uuid4())}


@router.put("/lessons/{lesson_id}/progress", response_model=dict)
def save_lesson_progress(
    lesson_id: int,
    payload: WatchedRangesRequest,
    db: Session = Depends(get_db),
    student=Depends(require_student),
):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found.")
    section = db.get(Section, lesson.section_id)
    course = db.get(Course, section.course_id) if section else None
    if course is None or not db.scalar(
        select(Enrollment.id).where(
            Enrollment.course_id == course.id,
            Enrollment.student_id == student.id,
        )
    ):
        raise HTTPException(403, "You are not enrolled in this course.")

    watched_seconds = 0.0
    merged = []
    for start, end in sorted(payload.watched_ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    watched_seconds = sum(end - start for start, end in merged)

    progress = db.scalar(
        select(LessonProgress).where(
            LessonProgress.student_id == student.id,
            LessonProgress.lesson_id == lesson_id,
        )
    )
    if progress is None:
        progress = LessonProgress(student_id=student.id, lesson_id=lesson_id)
        db.add(progress)

    progress.watched_seconds = int(watched_seconds)
    progress.completed = bool(lesson.duration_seconds and watched_seconds >= lesson.duration_seconds * 0.1)
    db.commit()
    db.refresh(progress)
    return {
        "last_position_seconds": payload.last_position_seconds,
        "watched_seconds": progress.watched_seconds,
        "watched_ranges": [list(item) for item in merged],
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
        completed = bool(progress.completed) if progress else False
        if completed:
            completed_count += 1
        rows.append({
            "lesson_id": lesson.id,
            "progress_percent": round(percent, 2),
            "completed": completed,
            "last_position_seconds": 0,
            "watched_seconds": watched,
            "watched_ranges": [],
        })
    overall = completed_count * 100 / len(lessons) if lessons else 0.0
    return {
        "course_id": course_id,
        "completion_threshold_percent": 10,
        "overall_percent": round(overall, 2),
        "lessons": rows,
    }
