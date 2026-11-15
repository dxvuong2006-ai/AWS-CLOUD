"""Tổng hợp chỉ số học tập theo khóa học."""

from sqlalchemy import Integer, case, func
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt
from app.models.section import Section
from app.models.tutor import TutorSession


def course_for_owner(db, course_id, instructor_id):
    """Tìm khóa học thuộc giảng viên."""
    return db.query(Course).filter(Course.id == course_id,
        Course.instructor_id == instructor_id).first()


def course_metrics(db, course_id):
    """Tính thống kê theo lượt thi và bản ghi tiến độ."""
    enrollments = db.query(func.count(Enrollment.id)).filter(
        Enrollment.course_id == course_id).scalar()
    attempts = (db.query(func.count(QuizAttempt.id),
                         func.sum(QuizAttempt.passed.cast(Integer)),
                         func.avg(QuizAttempt.score))
                .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
                .join(Section, Section.id == Quiz.section_id)
                .filter(Section.course_id == course_id).one())
    errors = (db.query(Question.id, Question.question,
                       func.count(QuizAnswer.id).label("incorrect_count"))
              .join(QuizAnswer, QuizAnswer.question_id == Question.id)
              .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
              .join(Quiz, Quiz.id == Question.quiz_id)
              .join(Section, Section.id == Quiz.section_id)
              .filter(Section.course_id == course_id,
                      QuizAnswer.is_correct.is_(False))
              .group_by(Question.id, Question.question)
              .order_by(func.count(QuizAnswer.id).desc(), Question.id)
              .limit(10).all())
    lessons = (db.query(func.count(Lesson.id)).join(
        Section, Section.id == Lesson.section_id).filter(
        Section.course_id == course_id,
        Lesson.status == "PUBLISHED").scalar())
    completed = (db.query(func.count(LessonProgress.id))
                 .join(Lesson, Lesson.id == LessonProgress.lesson_id)
                 .join(Section, Section.id == Lesson.section_id)
                 .join(Enrollment, (Enrollment.course_id == course_id) &
                       (Enrollment.student_id == LessonProgress.student_id))
                 .filter(Section.course_id == course_id,
                         Lesson.status == "PUBLISHED",
                         LessonProgress.completed.is_(True)).scalar())
    return enrollments, attempts, errors, lessons, completed


def student_course_checkpoint_stats(db, instructor_id, student_ids, course_ids):
    """Return checkpoint aggregates and latest result per enrolled student/course."""
    if not student_ids or not course_ids:
        return {}

    scope = (
        QuizAttempt.student_id.in_(student_ids),
        Course.id.in_(course_ids),
        Course.instructor_id == instructor_id,
        Enrollment.student_id == QuizAttempt.student_id,
    )
    aggregates = (
        db.query(
            QuizAttempt.student_id,
            Course.id.label("course_id"),
            func.count(QuizAttempt.id).label("attempt_count"),
            func.sum(case((QuizAttempt.passed.is_(True), 1), else_=0)).label("passed_attempts"),
            func.avg(QuizAttempt.score).label("average_score"),
        )
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(Section, Section.id == Quiz.section_id)
        .join(Course, Course.id == Section.course_id)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .filter(*scope)
        .group_by(QuizAttempt.student_id, Course.id)
        .all()
    )
    result = {}
    for row in aggregates:
        result[(row.student_id, row.course_id)] = {
            "attempt_count": int(row.attempt_count or 0),
            "passed_attempts": int(row.passed_attempts or 0),
            "average_score": float(row.average_score) if row.average_score is not None else None,
        }

    ranked = (
        db.query(
            QuizAttempt.student_id.label("student_id"),
            Course.id.label("course_id"),
            QuizAttempt.id.label("attempt_id"),
            QuizAttempt.score.label("score"),
            QuizAttempt.passed.label("passed"),
            QuizAttempt.created_at.label("created_at"),
            func.row_number().over(
                partition_by=(QuizAttempt.student_id, Course.id),
                order_by=(QuizAttempt.created_at.desc(), QuizAttempt.id.desc()),
            ).label("result_rank"),
        )
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(Section, Section.id == Quiz.section_id)
        .join(Course, Course.id == Section.course_id)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .filter(*scope)
        .subquery()
    )
    latest_rows = db.query(ranked).filter(ranked.c.result_rank == 1).all()
    for row in latest_rows:
        stats = result[(row.student_id, row.course_id)]
        stats.update({
            "last_score": float(row.score),
            "last_passed": bool(row.passed),
            "latest_attempt_id": row.attempt_id,
            "latest_at": row.created_at,
        })
    return result


def student_tutor_session_counts(db, instructor_id, student_ids, course_ids):
    """Count Tutor sessions only in the instructor's enrolled courses."""
    if not student_ids or not course_ids:
        return {}
    rows = (
        db.query(TutorSession.student_id, func.count(TutorSession.id))
        .join(Lesson, Lesson.id == TutorSession.lesson_id)
        .join(Section, Section.id == Lesson.section_id)
        .join(Course, Course.id == Section.course_id)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .filter(
            TutorSession.student_id.in_(student_ids),
            Enrollment.student_id == TutorSession.student_id,
            Course.id.in_(course_ids),
            Course.instructor_id == instructor_id,
        )
        .group_by(TutorSession.student_id)
        .all()
    )
    return {student_id: int(count) for student_id, count in rows}
