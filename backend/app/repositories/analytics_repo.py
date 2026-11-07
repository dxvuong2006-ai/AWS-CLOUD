"""Tổng hợp chỉ số học tập theo khóa học."""

from sqlalchemy import Integer, func
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt
from app.models.section import Section


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
