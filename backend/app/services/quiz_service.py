"""Student checkpoints. All grades and access decisions originate on the server."""
import hashlib
import json
from decimal import Decimal, ROUND_DOWN

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.question import Question
from app.models.quiz import CheckpointRemediation, Quiz, QuizAnswer, QuizAttempt
from app.models.section import Section
from app.models.user import User
from app.schemas.quiz import QuizAttemptResultResponse, QuizAttemptSubmitRequest
from app.schemas.quiz import QuizDetailResponse, QuestionResponse

PASS_SCORE = Decimal("80")  # UI Flow v4: fixed section-unlock threshold.
REMEDIATION_SCORE = Decimal("50")


def _context(db: Session, quiz_id: int, student_id: int):
    row = db.execute(
        select(Quiz, Section, Course).join(Section, Quiz.section_id == Section.id)
        .join(Course, Section.course_id == Course.id).where(Quiz.id == quiz_id)
        .with_for_update(read=True)
    ).first()
    if row is None:
        raise HTTPException(404, "Checkpoint not found.")
    quiz, section, course = row
    if course.status != "PUBLISHED":
        raise HTTPException(403, "Course is not published.")
    enrolled = db.scalar(select(Enrollment.id).where(
        Enrollment.student_id == student_id, Enrollment.course_id == course.id))
    if enrolled is None:
        raise HTTPException(403, "Course enrollment is required.")
    return quiz, section, course


def _latest(db: Session, student_id: int, quiz_id: int):
    return db.scalar(select(QuizAttempt).where(
        QuizAttempt.student_id == student_id, QuizAttempt.quiz_id == quiz_id
    ).order_by(QuizAttempt.attempt_number.desc()).limit(1))


def can_retry(db: Session, attempt: QuizAttempt | None) -> bool:
    if attempt is None:
        return True
    review = db.get(CheckpointRemediation, attempt.id)
    if review is None:
        return attempt.score >= REMEDIATION_SCORE
    return bool(review and review.explanation_completed and review.review_completed
                and review.practice_total in (2, 3)
                and review.practice_correct * 3 >= review.practice_total * 2)


def _eligibility(db: Session, quiz, section, student_id, lesson_id):
    if not quiz.is_approved:
        raise HTTPException(404, "No approved checkpoint is available.")
    prior = db.scalars(select(Section).where(
        Section.course_id == section.course_id, Section.position < section.position
    )).all()
    for previous in prior:
        passed = db.scalar(select(QuizAttempt.id).join(Quiz).where(
            Quiz.section_id == previous.id, Quiz.is_approved.is_(True),
            QuizAttempt.student_id == student_id, QuizAttempt.passed.is_(True)
        ).limit(1))
        if passed is None:
            raise HTTPException(403, "Pass the previous section checkpoint first.")
    completed = select(LessonProgress.id).join(
        Lesson, Lesson.id == LessonProgress.lesson_id
    ).where(Lesson.section_id == section.id, Lesson.status == "PUBLISHED",
            LessonProgress.student_id == student_id, LessonProgress.completed.is_(True))
    if lesson_id is not None:
        completed = completed.where(Lesson.id == lesson_id)
    if db.scalar(completed.limit(1)) is None:
        raise HTTPException(403, "Complete the current lesson before this checkpoint.")
    latest = _latest(db, student_id, quiz.id)
    if not can_retry(db, latest):
        raise HTTPException(403, "Mandatory AI review and practice must be completed before retrying.")
    return latest


def get_checkpoint(db: Session, section_id: int, student_id: int, lesson_id=None):
    quiz_id = db.scalar(select(Quiz.id).where(Quiz.section_id == section_id))
    if quiz_id is None:
        raise HTTPException(404, "Checkpoint not found.")
    quiz, section, _ = _context(db, quiz_id, student_id)
    latest = _eligibility(db, quiz, section, student_id, lesson_id)
    questions = db.scalars(select(Question).where(Question.quiz_id == quiz.id)
                           .order_by(Question.position)).all()
    if not questions:
        raise HTTPException(404, "Checkpoint has no approved questions.")
    # Explicit public DTO: correct_answer and explanation are never serialized.
    return QuizDetailResponse(
        id=quiz.id, section_id=section.id, title=quiz.title, passing_score=PASS_SCORE,
        is_approved=True, created_at=quiz.created_at, updated_at=quiz.updated_at,
        questions=[QuestionResponse.model_validate(q) for q in questions],
        attempt_count=latest.attempt_number if latest else 0,
        previous_score=latest.score if latest else None, can_retry=True,
    )


def _result(db: Session, attempt: QuizAttempt):
    answers = db.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id)
                         .order_by(QuizAnswer.question_id)).all()
    review_required = not can_retry(db, _latest(db, attempt.student_id, attempt.quiz_id))
    quiz = db.get(Quiz, attempt.quiz_id)
    section = db.get(Section, quiz.section_id)
    try:
        _eligibility(db, quiz, section, attempt.student_id, None)
        allowed = True
    except HTTPException:
        allowed = False
    return QuizAttemptResultResponse(
        id=attempt.id, student_id=attempt.student_id, quiz_id=attempt.quiz_id,
        score=attempt.score, passed=attempt.passed, attempt_number=attempt.attempt_number,
        created_at=attempt.created_at, can_retry=allowed, remediation_required=review_required,
        answers=[dict(question_id=a.question_id, selected_answer=a.selected_answer,
                      is_correct=a.is_correct) for a in answers],
    )


def _fingerprint(payload):
    canonical = {"lesson_id": payload.lesson_id, "answers": sorted(
        (a.question_id, a.selected_answer) for a in payload.answers
        if a.selected_answer is not None)}
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False,
                                     sort_keys=True).encode("utf-8")).hexdigest()


def _existing(db, student_id, quiz_id, request_id):
    return db.scalar(select(QuizAttempt).where(
        QuizAttempt.student_id == student_id, QuizAttempt.quiz_id == quiz_id,
        QuizAttempt.request_id == request_id))


def _replay(db, attempt, fingerprint):
    if attempt.request_hash != fingerprint:
        raise HTTPException(409, "Request ID was already used with different answers.")
    return _result(db, attempt)


def submit_attempt(db: Session, quiz_id: int, student_id: int,
                   payload: QuizAttemptSubmitRequest):
    request_id, fingerprint = str(payload.request_id), _fingerprint(payload)
    try:
        # PostgreSQL row lock serializes submissions from this student, including
        # first attempts and concurrent different keys. No process-local mutex.
        student = db.scalar(select(User).where(User.id == student_id).with_for_update())
        if student is None or student.role != "STUDENT":
            raise HTTPException(403, "Student role required.")
        quiz, section, _ = _context(db, quiz_id, student_id)
        existing = _existing(db, student_id, quiz_id, request_id)
        if existing is not None:
            result = _replay(db, existing, fingerprint)
            db.commit()
            return result
        latest = _eligibility(db, quiz, section, student_id, payload.lesson_id)
        questions = db.scalars(select(Question).where(Question.quiz_id == quiz_id)
                               .order_by(Question.position).with_for_update(read=True)).all()
        if not questions:
            raise HTTPException(404, "Checkpoint has no approved questions.")
        by_id = {q.id: q for q in questions}
        selected = {}
        for answer in payload.answers:
            question = by_id.get(answer.question_id)
            if question is None or answer.question_id in selected:
                raise HTTPException(422, "Unknown or duplicate question.")
            if answer.selected_answer is not None and answer.selected_answer not in question.options_json:
                raise HTTPException(422, "Invalid option for this question.")
            selected[answer.question_id] = answer.selected_answer
        correct = sum(selected.get(q.id) == q.correct_answer for q in questions)
        raw_score = Decimal(correct * 100) / Decimal(len(questions))
        # Do not display 80.00 for a raw score just below the pass threshold.
        score = raw_score.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        attempt = QuizAttempt(student_id=student_id, quiz_id=quiz_id, score=score,
                              passed=raw_score >= PASS_SCORE,
                              attempt_number=latest.attempt_number + 1 if latest else 1,
                              request_id=request_id, request_hash=fingerprint)
        db.add(attempt)
        db.flush()
        db.add_all([QuizAnswer(attempt_id=attempt.id, question_id=q.id,
                               selected_answer=selected.get(q.id),
                               is_correct=selected.get(q.id) == q.correct_answer)
                    for q in questions])
        if raw_score < REMEDIATION_SCORE:
            db.add(CheckpointRemediation(attempt_id=attempt.id))
        db.flush()
        result = _result(db, attempt)
        db.commit()  # Grade, every answer, and remediation obligation are atomic.
        return result
    except IntegrityError:
        db.rollback()
        # Unique request key is a final DB-level guard, including retried writes.
        _context(db, quiz_id, student_id)
        existing = _existing(db, student_id, quiz_id, request_id)
        if existing is not None:
            return _replay(db, existing, fingerprint)
        raise HTTPException(409, "Concurrent submission; retry with the same request ID.") from None
    except Exception:
        db.rollback()
        raise


def attempt_history(db: Session, quiz_id: int, student_id: int, limit=20, offset=0):
    _context(db, quiz_id, student_id)
    attempts = db.scalars(select(QuizAttempt).where(
        QuizAttempt.student_id == student_id, QuizAttempt.quiz_id == quiz_id
    ).order_by(QuizAttempt.attempt_number.desc()).limit(limit).offset(offset)).all()
    return [_result(db, attempt) for attempt in attempts]
