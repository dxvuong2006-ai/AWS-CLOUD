"""Endpoint thống kê khóa học cho giảng viên."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_instructor
from app.services import analytics_service
from app.models.course import Course
from app.models.section import Section
from app.models.lesson import Lesson
from app.models.enrollment import Enrollment
from app.models.progress import LessonProgress
from app.models.user import User
from sqlalchemy import select, func

router = APIRouter(tags=["Analytics"])


@router.get("/instructor/dashboard")
def get_instructor_dashboard(
    db: Session = Depends(get_db),
    instructor=Depends(require_instructor),
):
    course_ids = list(db.scalars(
        select(Course.id).where(Course.instructor_id == instructor.id)
    ).all())
    published = db.scalar(
        select(func.count(Course.id)).where(
            Course.instructor_id == instructor.id,
            Course.status == "PUBLISHED",
        )
    ) or 0
    lessons = db.scalar(
        select(func.count(Lesson.id))
        .join(Section, Section.id == Lesson.section_id)
        .where(
            Section.course_id.in_(course_ids),
            Lesson.status == "PUBLISHED",
        )
    ) if course_ids else 0
    review_required = db.scalar(
        select(func.count(Lesson.id))
        .join(Section, Section.id == Lesson.section_id)
        .where(
            Section.course_id.in_(course_ids),
            Lesson.status == "REVIEW_REQUIRED",
        )
    ) if course_ids else 0
    students = db.scalar(
        select(func.count(func.distinct(Enrollment.student_id))).where(
            Enrollment.course_id.in_(course_ids)
        )
    ) if course_ids else 0
    courses = db.scalars(
        select(Course).where(Course.instructor_id == instructor.id)
        .order_by(Course.updated_at.desc(), Course.id.desc()).limit(8)
    ).all()
    return {
        "published_courses": published,
        "lesson_count": lessons,
        "review_required": review_required,
        "active_students": students,
        "courses": [
            {
                "id": course.id,
                "title": course.title,
                "status": course.status,
                "lesson_count": db.scalar(
                    select(func.count(Lesson.id))
                    .join(Section, Section.id == Lesson.section_id)
                    .where(Section.course_id == course.id)
                ) or 0,
            }
            for course in courses
        ],
    }


@router.get("/instructor/courses/{course_id}/analytics")
def get_course_analytics(course_id: int, db: Session = Depends(get_db),
                         instructor=Depends(require_instructor)):
    """Trả thống kê của khóa học thuộc giảng viên."""
    result = analytics_service.get_course_analytics(db, course_id, instructor.id)
    if result is None:
        raise HTTPException(404, "Course not found.")
    return result


@router.get("/instructor/students")
def list_instructor_students(
    db: Session = Depends(get_db),
    instructor=Depends(require_instructor),
):
    course_ids = list(db.scalars(
        select(Course.id).where(Course.instructor_id == instructor.id)
    ).all())
    if not course_ids:
        return []

    enrollments = db.scalars(
        select(Enrollment).where(Enrollment.course_id.in_(course_ids))
        .order_by(Enrollment.enrolled_at.desc())
    ).all()
    students = {}
    for enrollment in enrollments:
        user = db.get(User, enrollment.student_id)
        if user is None or user.id in students:
            continue
        lesson_ids = list(db.scalars(
            select(Lesson.id)
            .join(Section, Section.id == Lesson.section_id)
            .where(Section.course_id == enrollment.course_id, Lesson.status == "PUBLISHED")
        ).all())
        completed = db.scalar(
            select(func.count(LessonProgress.id)).where(
                LessonProgress.student_id == user.id,
                LessonProgress.lesson_id.in_(lesson_ids),
                LessonProgress.completed.is_(True),
            )
        ) if lesson_ids else 0
        progress = round(completed * 100 / len(lesson_ids), 2) if lesson_ids else 0.0
        students[user.id] = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "progress": progress,
            "status": "COMPLETED" if lesson_ids and completed >= len(lesson_ids) else "IN_PROGRESS",
        }
    return list(students.values())


@router.get("/instructor/students/{student_id}")
def get_instructor_student(
    student_id: int,
    db: Session = Depends(get_db),
    instructor=Depends(require_instructor),
):
    user = db.get(User, student_id)
    if user is None or user.role != "STUDENT":
        raise HTTPException(404, "Student not found.")
    course_ids = list(db.scalars(
        select(Course.id).where(Course.instructor_id == instructor.id)
    ).all())
    enrollments = db.scalars(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.course_id.in_(course_ids),
        )
    ).all() if course_ids else []
    courses = []
    for enrollment in enrollments:
        course = db.get(Course, enrollment.course_id)
        if course is None:
            continue
        lesson_ids = list(db.scalars(
            select(Lesson.id)
            .join(Section, Section.id == Lesson.section_id)
            .where(Section.course_id == course.id, Lesson.status == "PUBLISHED")
        ).all())
        completed = db.scalar(
            select(func.count(LessonProgress.id)).where(
                LessonProgress.student_id == student_id,
                LessonProgress.lesson_id.in_(lesson_ids),
                LessonProgress.completed.is_(True),
            )
        ) if lesson_ids else 0
        courses.append({
            "id": course.id,
            "title": course.title,
            "progress": round(completed * 100 / len(lesson_ids), 2) if lesson_ids else 0.0,
            "status": "COMPLETED" if lesson_ids and completed >= len(lesson_ids) else "IN_PROGRESS",
        })
    if not courses:
        raise HTTPException(404, "Student has no enrollments in your courses.")
    return {"id": user.id, "name": user.name, "email": user.email, "courses": courses}
