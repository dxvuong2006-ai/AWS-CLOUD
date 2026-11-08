"""Truy vấn và lưu dữ liệu Tutor."""

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt
from app.models.section import Section
from app.models.tutor import TutorMessage, TutorSession


def attempt_context(db, attempt_id, student_id):
    """Tìm lần thi của học viên và các câu trả lời sai."""
    row = (db.query(QuizAttempt, Quiz, Section, Course)
           .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
           .join(Section, Section.id == Quiz.section_id)
           .join(Course, Course.id == Section.course_id)
           .join(Enrollment, (Enrollment.course_id == Course.id) &
                 (Enrollment.student_id == student_id))
           .filter(QuizAttempt.id == attempt_id,
                   QuizAttempt.student_id == student_id,
                   Course.status == "PUBLISHED").first())
    if row is None:
        return None
    attempt, quiz, section, course = row
    lesson = (db.query(Lesson).filter(
        Lesson.section_id == section.id,
        Lesson.status.in_(("APPROVED", "PUBLISHED")),
    ).order_by(Lesson.position, Lesson.id).first())
    questions = (db.query(Question, QuizAnswer)
                 .outerjoin(QuizAnswer, (QuizAnswer.question_id == Question.id) &
                            (QuizAnswer.attempt_id == attempt.id))
                 .filter(Question.quiz_id == quiz.id)
                 .order_by(Question.position).all())
    return attempt, lesson, questions


def get_session(db, session_id, student_id, lock=False):
    """Tìm phiên thuộc học viên và khóa hàng khi cập nhật."""
    query = (db.query(TutorSession)
             .join(Lesson, Lesson.id == TutorSession.lesson_id)
             .join(Section, Section.id == Lesson.section_id)
             .join(Course, Course.id == Section.course_id)
             .join(Enrollment, (Enrollment.course_id == Course.id) &
                   (Enrollment.student_id == student_id))
             .filter(TutorSession.id == session_id,
                     TutorSession.student_id == student_id,
                     Course.status == "PUBLISHED",
                     Lesson.status.in_(("APPROVED", "PUBLISHED"))))
    if lock:
        query = query.with_for_update()
    return query.first()


def get_lesson(db, lesson_id):
    """Lấy bài học theo mã."""
    return db.query(Lesson).filter(Lesson.id == lesson_id).first()


def save_session(db, session, explanation):
    """Lưu phiên và lời giải trong một giao dịch."""
    try:
        db.add(session)
        db.flush()
        db.add(TutorMessage(session_id=session.id, role="ASSISTANT",
                            content=explanation))
        db.commit()
        db.refresh(session)
        return session
    except Exception:
        db.rollback()
        raise


def save_messages(db, session_id, question, answer):
    """Lưu cặp hội thoại nguyên tử."""
    try:
        db.add_all([TutorMessage(session_id=session_id, role="USER", content=question),
                    TutorMessage(session_id=session_id, role="ASSISTANT", content=answer)])
        db.commit()
    except Exception:
        db.rollback()
        raise


def complete(db, session):
    """Đánh dấu đã hoàn thành phiên ôn tập."""
    try:
        session.remediation_completed = True
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_attempt_owner(db, attempt_id):
    """Lấy chủ sở hữu lượt thi; trả None nếu không tồn tại."""
    return db.query(QuizAttempt.student_id).filter(
        QuizAttempt.id == attempt_id,
    ).scalar()


def get_session_owner(db, session_id):
    """Lấy chủ sở hữu phiên; trả None nếu không tồn tại."""
    return db.query(TutorSession.student_id).filter(
        TutorSession.id == session_id,
    ).scalar()


def question_failure_rates(db, course_id):
    """Tổng hợp tỷ lệ sai và chủ đề từng câu trong khóa học."""
    from sqlalchemy import case, func

    failures = func.sum(case((QuizAnswer.is_correct.is_(False), 1), else_=0))
    total = func.count(QuizAnswer.id)
    return (
        db.query(Question.id, Question.question, Question.topic,
                 failures.label("incorrect_count"), total.label("answer_count"))
        .join(QuizAnswer, QuizAnswer.question_id == Question.id)
        .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
        .join(Quiz, Quiz.id == Question.quiz_id)
        .join(Section, Section.id == Quiz.section_id)
        .filter(Section.course_id == course_id,
                QuizAttempt.quiz_id == Question.quiz_id)
        .group_by(Question.id, Question.question, Question.topic)
        .all()
    )



def get_approved_section_lessons(db, lesson_id):
    """Lấy các bài đã duyệt trong cùng section với phiên Tutor."""
    section_id = db.query(Lesson.section_id).filter(Lesson.id == lesson_id).scalar()
    return (db.query(Lesson)
            .filter(Lesson.section_id == section_id,
                    Lesson.status.in_(("APPROVED", "PUBLISHED")))
            .order_by(Lesson.position, Lesson.id).all())
