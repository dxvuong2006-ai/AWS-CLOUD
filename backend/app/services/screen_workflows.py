"""Read models for instructor management and student completion."""
from fastapi import HTTPException
from sqlalchemy import func
from app.models.course import Course
from app.models.section import Section
from app.models.lesson import Lesson
from app.models.enrollment import Enrollment
from app.models.progress import LessonProgress
from app.models.quiz import Quiz, QuizAttempt
from app.models.user import User
from app.repositories import analytics_repo
from app.services import analytics_service
from app.schemas.lesson import LessonVideoFields
from app.services.upload_service import pending_upload_metadata


def course_detail(db, course):
    sections = db.query(Section).filter(Section.course_id == course.id).order_by(Section.position, Section.id).all()
    return {**{c.name: getattr(course, c.name) for c in course.__table__.columns},
            "sections": [{"id": s.id, "title": s.title, "position": s.position,
                "lessons": [{"id": l.id, "title": l.title, "position": l.position,
                             **LessonVideoFields.model_validate(l).model_copy(
                                 update=pending_upload_metadata(db, l)).model_dump(mode="json")}
                    for l in db.query(Lesson).filter(Lesson.section_id == s.id).order_by(Lesson.position, Lesson.id)]}
                for s in sections]}


def owned_course(db, instructor_id, course_id):
    course = db.query(Course).filter(Course.id == course_id, Course.instructor_id == instructor_id).first()
    if course is None:
        raise HTTPException(404, "Không tìm thấy khóa học của bạn.")
    return course


def instructor_courses(db, instructor_id):
    return [course_detail(db, c) for c in db.query(Course).filter(
        Course.instructor_id == instructor_id).order_by(Course.updated_at.desc(), Course.id.desc())]


def queue(db, instructor_id):
    return [{"id": l.id, "title": l.title, "status": l.status, "course_id": c.id, "course_title": c.title}
        for l, c in db.query(Lesson, Course).join(Section, Section.id == Lesson.section_id)
        .join(Course, Course.id == Section.course_id).filter(Course.instructor_id == instructor_id,
            Lesson.status.in_(["REVIEW_REQUIRED", "FAILED", "PROCESSING", "TRANSCRIBING", "AI_PROCESSING", "UPLOADED"]))
        .order_by(Lesson.updated_at.desc(), Lesson.id.desc())]


def dashboard(db, instructor_id):
    courses = instructor_courses(db, instructor_id)
    metrics = [analytics_service.get_course_analytics(db, c["id"], instructor_id) for c in courses]
    total = sum(m["attempt_count"] for m in metrics)
    tasks = queue(db, instructor_id)
    ids = [c["id"] for c in courses]
    students = db.query(func.count(func.distinct(Enrollment.student_id))).filter(Enrollment.course_id.in_(ids)).scalar()
    return {"published_courses": sum(c["status"] == "PUBLISHED" for c in courses),
        "course_count": len(courses), "lesson_count": sum(len(s["lessons"]) for c in courses for s in c["sections"]),
        "review_required": sum(t["status"] == "REVIEW_REQUIRED" for t in tasks),
        "active_students": students, "pass_rate": round(100 * sum(m["passed_attempts"] for m in metrics) / total) if total else None,
        "courses": [{**c, "lesson_count": sum(len(s["lessons"]) for s in c["sections"])} for c in courses[:5]],
        "tasks": tasks[:6]}


def instructor_students(db, instructor_id, course_id=None):
    if course_id is not None:
        owned_course(db, instructor_id, course_id)
    course_ids = [course_id] if course_id is not None else [
        row[0] for row in db.query(Course.id).filter(
            Course.instructor_id == instructor_id).all()
    ]
    if not course_ids:
        return []
    rows = db.query(User).join(Enrollment, Enrollment.student_id == User.id).filter(
        Enrollment.course_id.in_(course_ids), User.role == "STUDENT").distinct().all()
    checkpoint_metrics = analytics_repo.student_course_checkpoint_stats(
        db, instructor_id, [student.id for student in rows], course_ids,
    )
    result = []
    for student in rows:
        courses = db.query(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(
            Enrollment.student_id == student.id, Course.instructor_id == instructor_id,
            Course.id.in_(course_ids)).all()
        completion_rows = [completion(db, student.id, course.id) for course in courses]
        lesson_count = sum(detail["lesson_count"] for detail in completion_rows)
        completed_count = sum(detail["completed_lessons"] for detail in completion_rows)
        progress = round(100 * completed_count / lesson_count) if lesson_count else 0
        student_metrics = [
            checkpoint_metrics[(student.id, course.id)]
            for course in courses
            if (student.id, course.id) in checkpoint_metrics
        ]
        checkpoint = checkpoint_summary(student_metrics)
        result.append({"id": student.id, "name": student.name, "email": student.email,
                       "progress": progress,
                       "attempt_count": checkpoint["attempt_count"],
                       "passed_attempts": checkpoint["passed_attempts"],
                       "pass_rate": checkpoint["pass_rate"],
                       "last_score": checkpoint["last_score"],
                       "last_passed": checkpoint["last_passed"],
                       "status": "COMPLETED" if progress == 100 else "ACTIVE"})
    return result


def instructor_student(db, instructor_id, student_id):
    student = db.query(User).filter(User.id == student_id, User.role == "STUDENT").first()
    if student is None:
        raise HTTPException(404, "Không tìm thấy học viên.")
    courses = db.query(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(
        Enrollment.student_id == student_id, Course.instructor_id == instructor_id).all()
    if not courses:
        raise HTTPException(404, "Học viên không thuộc khóa học của bạn.")
    details = [completion(db, student_id, course.id) for course in courses]
    course_ids = [course.id for course in courses]
    metrics = analytics_repo.student_course_checkpoint_stats(
        db, instructor_id, [student_id], course_ids,
    )
    course_metrics = [metrics[(student_id, course.id)]
                      for course in courses
                      if (student_id, course.id) in metrics]
    checkpoint = checkpoint_summary(course_metrics)
    tutor_counts = analytics_repo.student_tutor_session_counts(
        db, instructor_id, [student_id], course_ids,
    )
    total_lessons = sum(detail["lesson_count"] for detail in details)
    total_completed = sum(detail["completed_lessons"] for detail in details)
    return {"id": student.id, "name": student.name, "email": student.email,
            "courses": [{"id": course.id, "title": course.title,
                         "progress": course_progress_percent(detail),
                         **checkpoint_summary(
                             [metrics[(student_id, course.id)]]
                             if (student_id, course.id) in metrics else []
                         )}
                        for course, detail in zip(courses, details)],
            "progress": round(100 * total_completed / total_lessons) if total_lessons else 0,
            "attempt_count": checkpoint["attempt_count"],
            "passed_attempts": checkpoint["passed_attempts"],
            "pass_rate": checkpoint["pass_rate"],
            "average_score": checkpoint["average_score"],
            "last_score": checkpoint["last_score"],
            "last_passed": checkpoint["last_passed"],
            "tutor_sessions": tutor_counts.get(student_id, 0),
            "weak_concepts": []}


def student_course(db, student_id, course_id):
    course = db.query(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(
        Course.id == course_id, Enrollment.student_id == student_id, Course.status == "PUBLISHED").first()
    if course is None:
        raise HTTPException(404, "Không tìm thấy khóa học đã đăng ký.")
    return course


def completion(db, student_id, course_id):
    course = student_course(db, student_id, course_id)
    sections = db.query(Section).filter(Section.course_id == course_id).all()
    lessons = db.query(Lesson).join(Section).filter(Section.course_id == course_id, Lesson.status == "PUBLISHED").all()
    done = {p.lesson_id for p in db.query(LessonProgress).filter(
        LessonProgress.student_id == student_id, LessonProgress.completed.is_(True))}
    passed_sections, scores = 0, []
    for section in sections:
        quiz = db.query(Quiz).filter(Quiz.section_id == section.id, Quiz.is_approved.is_(True)).first()
        best = db.query(func.max(QuizAttempt.score)).filter(
            QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == student_id,
            QuizAttempt.passed.is_(True)).scalar() if quiz else None
        if best is not None and best >= 80:
            passed_sections += 1
            scores.append(float(best))
    return {"course_id": course.id, "title": course.title, "section_count": len(sections),
        "passed_sections": passed_sections, "lesson_count": len(lessons),
        "completed_lessons": sum(l.id in done for l in lessons),
        "average_score": round(sum(scores) / len(scores)) if scores else None,
        "completed": bool(sections and lessons) and passed_sections == len(sections) and all(l.id in done for l in lessons)}


def course_progress_percent(detail):
    """Derive the course progress value from the completion read-model contract."""
    lesson_count = detail["lesson_count"]
    return round(100 * detail["completed_lessons"] / lesson_count) if lesson_count else 0


def checkpoint_summary(course_metrics):
    """Combine attempts without conflating checkpoint outcomes with video progress."""
    attempt_count = sum(item["attempt_count"] for item in course_metrics)
    passed_attempts = sum(item["passed_attempts"] for item in course_metrics)
    score_total = sum(
        item["average_score"] * item["attempt_count"]
        for item in course_metrics if item["average_score"] is not None
    )
    latest = max(
        (item for item in course_metrics if item.get("latest_at") is not None),
        key=lambda item: (item["latest_at"], item["latest_attempt_id"]),
        default=None,
    )
    return {
        "attempt_count": attempt_count,
        "passed_attempts": passed_attempts,
        "pass_rate": round(100 * passed_attempts / attempt_count, 2) if attempt_count else None,
        "average_score": round(score_total / attempt_count, 2) if attempt_count else None,
        "last_score": latest.get("last_score") if latest else None,
        "last_passed": latest.get("last_passed") if latest else None,
    }


def history(db, student_id, offset, limit):
    rows = (db.query(QuizAttempt, Quiz, Section, Course)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id).join(Section, Section.id == Quiz.section_id)
        .join(Course, Course.id == Section.course_id).filter(QuizAttempt.student_id == student_id)
        .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id.desc()).offset(offset).limit(limit).all())
    return [{"id": a.id, "quiz_id": q.id, "course_id": c.id, "course_title": c.title,
        "section_id": s.id, "section_title": s.title, "score": float(a.score),
        "passed": a.passed, "attempt_number": a.attempt_number} for a,q,s,c in rows]


def overview(db, student_id):
    courses = db.query(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(
        Enrollment.student_id == student_id, Course.status == "PUBLISHED").order_by(Course.id).all()
    result = []
    for course in courses:
        summary = completion(db, student_id, course.id)
        lessons = db.query(Lesson).join(Section).filter(
            Section.course_id == course.id, Lesson.status == "PUBLISHED").all()
        progress = {p.lesson_id: p for p in db.query(LessonProgress).filter(
            LessonProgress.student_id == student_id, LessonProgress.lesson_id.in_([l.id for l in lessons]))}
        percentages = [100 if progress.get(l.id) and progress[l.id].completed else
            min(100, int(100 * progress[l.id].watched_seconds / l.duration_seconds))
            if progress.get(l.id) and l.duration_seconds else 0 for l in lessons]
        result.append({**summary, "progress_percent": sum(percentages) // len(percentages) if percentages else 0})
    return result
