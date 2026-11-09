"""Student checkpoint and quiz submission business logic.

All grading, unlock checks, attempt numbering, replay protection, and
remediation decisions are made by this service.
"""

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
from app.models.quiz import (
    CheckpointRemediation,
    MIN_PASSING_SCORE,
    Quiz,
    QuizAnswer,
    QuizAttempt,
)
from app.models.section import Section
from app.models.user import User
from app.repositories import quizzes_repo
from app.schemas.quiz import (
    QuestionResponse,
    QuizAttemptResultResponse,
    QuizAttemptSubmitRequest,
    QuizDetailResponse,
    QuizSubmitRequest,
)
from app.services import unlock_service
from app.services.unlock_service import SectionLockedError


PASS_SCORE = Decimal("80")
REMEDIATION_SCORE = Decimal("50")


class QuizNotFoundError(Exception):
    pass


class QuizNotApprovedError(Exception):
    pass


class QuizAccessDeniedError(Exception):
    pass


class InvalidSubmissionError(Exception):
    pass


def _context(db: Session, quiz_id: int, student_id: int):
    row = db.execute(
        select(Quiz, Section, Course)
        .join(Section, Quiz.section_id == Section.id)
        .join(Course, Section.course_id == Course.id)
        .where(Quiz.id == quiz_id)
        .with_for_update(read=True)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found.")

    quiz, section, course = row
    if course.status != "PUBLISHED":
        raise HTTPException(status_code=403, detail="Course is not published.")

    enrolled = db.scalar(
        select(Enrollment.id).where(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course.id,
        )
    )
    if enrolled is None:
        raise HTTPException(status_code=403, detail="Course enrollment is required.")
    return quiz, section, course


def _latest(db: Session, student_id: int, quiz_id: int) -> QuizAttempt | None:
    return db.scalar(
        select(QuizAttempt)
        .where(
            QuizAttempt.student_id == student_id,
            QuizAttempt.quiz_id == quiz_id,
        )
        .order_by(QuizAttempt.attempt_number.desc())
        .limit(1)
    )


def can_retry(db: Session, attempt: QuizAttempt | None) -> bool:
    if attempt is None:
        return True

    review = db.get(CheckpointRemediation, attempt.id)
    if review is None:
        return attempt.score >= REMEDIATION_SCORE

    return bool(
        review.explanation_completed
        and review.review_completed
        and review.practice_total in (2, 3)
        and review.practice_correct * 3 >= review.practice_total * 2
    )


def _eligibility(
    db: Session,
    quiz: Quiz,
    section: Section,
    student_id: int,
    lesson_id: int | None,
) -> QuizAttempt | None:
    if not quiz.is_approved:
        raise HTTPException(status_code=404, detail="No approved checkpoint is available.")

    prior_sections = db.scalars(
        select(Section).where(
            Section.course_id == section.course_id,
            Section.position < section.position,
        )
    ).all()
    for previous in prior_sections:
        passed = db.scalar(
            select(QuizAttempt.id)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                Quiz.section_id == previous.id,
                Quiz.is_approved.is_(True),
                QuizAttempt.student_id == student_id,
                QuizAttempt.passed.is_(True),
            )
            .limit(1)
        )
        if passed is None:
            raise HTTPException(
                status_code=403,
                detail="Pass the previous section checkpoint first.",
            )

    completed_query = (
        select(LessonProgress.id)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .where(
            Lesson.section_id == section.id,
            Lesson.status == "PUBLISHED",
            LessonProgress.student_id == student_id,
            LessonProgress.completed.is_(True),
        )
    )
    if lesson_id is not None:
        completed_query = completed_query.where(Lesson.id == lesson_id)
    if db.scalar(completed_query.limit(1)) is None:
        raise HTTPException(
            status_code=403,
            detail="Complete the current lesson before this checkpoint.",
        )

    latest = _latest(db, student_id, quiz.id)
    if not can_retry(db, latest):
        raise HTTPException(
            status_code=403,
            detail="Mandatory AI review and practice must be completed before retrying.",
        )
    return latest


def get_checkpoint(
    db: Session,
    section_id: int,
    student_id: int,
    lesson_id: int | None = None,
) -> QuizDetailResponse:
    quiz_id = db.scalar(select(Quiz.id).where(Quiz.section_id == section_id))
    if quiz_id is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found.")

    quiz, section, _ = _context(db, quiz_id, student_id)
    latest = _eligibility(db, quiz, section, student_id, lesson_id)
    questions = db.scalars(
        select(Question)
        .where(Question.quiz_id == quiz.id)
        .order_by(Question.position)
    ).all()
    if not questions:
        raise HTTPException(status_code=404, detail="Checkpoint has no approved questions.")

    return QuizDetailResponse(
        id=quiz.id,
        section_id=section.id,
        title=quiz.title,
        passing_score=PASS_SCORE,
        is_approved=True,
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
        questions=[QuestionResponse.model_validate(question) for question in questions],
        attempt_count=latest.attempt_number if latest else 0,
        previous_score=latest.score if latest else None,
        can_retry=True,
    )


def _result(db: Session, attempt: QuizAttempt) -> QuizAttemptResultResponse:
    answers = db.scalars(
        select(QuizAnswer)
        .where(QuizAnswer.attempt_id == attempt.id)
        .order_by(QuizAnswer.question_id)
    ).all()

    quiz = db.get(Quiz, attempt.quiz_id)
    section = db.get(Section, quiz.section_id)
    review_required = not can_retry(db, _latest(db, attempt.student_id, attempt.quiz_id))
    try:
        _eligibility(db, quiz, section, attempt.student_id, None)
        allowed = True
    except HTTPException:
        allowed = False

    return QuizAttemptResultResponse(
        id=attempt.id,
        student_id=attempt.student_id,
        quiz_id=attempt.quiz_id,
        score=attempt.score,
        passed=attempt.passed,
        attempt_number=attempt.attempt_number,
        created_at=attempt.created_at,
        answers=[
            {
                "question_id": answer.question_id,
                "selected_answer": answer.selected_answer,
                "is_correct": answer.is_correct,
            }
            for answer in answers
        ],
        can_retry=allowed,
        remediation_required=review_required,
    )


def _fingerprint(payload: QuizAttemptSubmitRequest) -> str:
    canonical = {
        "lesson_id": payload.lesson_id,
        "answers": sorted(
            (answer.question_id, answer.selected_answer)
            for answer in payload.answers
            if answer.selected_answer is not None
        ),
    }
    return hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _existing(
    db: Session,
    student_id: int,
    quiz_id: int,
    request_id: str,
) -> QuizAttempt | None:
    return db.scalar(
        select(QuizAttempt).where(
            QuizAttempt.student_id == student_id,
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.request_id == request_id,
        )
    )


def _replay(
    db: Session,
    attempt: QuizAttempt,
    fingerprint: str,
) -> QuizAttemptResultResponse:
    if attempt.request_hash != fingerprint:
        raise HTTPException(
            status_code=409,
            detail="Request ID was already used with different answers.",
        )
    return _result(db, attempt)


def submit_attempt(
    db: Session,
    quiz_id: int,
    student_id: int,
    payload: QuizAttemptSubmitRequest,
) -> QuizAttemptResultResponse:
    request_id = str(payload.request_id)
    fingerprint = _fingerprint(payload)
    try:
        student = db.scalar(
            select(User).where(User.id == student_id).with_for_update()
        )
        if student is None or student.role != "STUDENT":
            raise HTTPException(status_code=403, detail="Student role required.")

        quiz, section, _ = _context(db, quiz_id, student_id)
        existing = _existing(db, student_id, quiz_id, request_id)
        if existing is not None:
            result = _replay(db, existing, fingerprint)
            db.commit()
            return result

        latest = _eligibility(
            db,
            quiz,
            section,
            student_id,
            payload.lesson_id,
        )
        questions = db.scalars(
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.position)
            .with_for_update(read=True)
        ).all()
        if not questions:
            raise HTTPException(
                status_code=404,
                detail="Checkpoint has no approved questions.",
            )

        by_id = {question.id: question for question in questions}
        selected: dict[int, str | None] = {}
        for answer in payload.answers:
            question = by_id.get(answer.question_id)
            if question is None or answer.question_id in selected:
                raise HTTPException(status_code=422, detail="Unknown or duplicate question.")
            if (
                answer.selected_answer is not None
                and answer.selected_answer not in question.options_json
            ):
                raise HTTPException(status_code=422, detail="Invalid option for this question.")
            selected[answer.question_id] = answer.selected_answer

        correct = sum(
            selected.get(question.id) == question.correct_answer
            for question in questions
        )
        raw_score = Decimal(correct * 100) / Decimal(len(questions))
        score = raw_score.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        attempt = QuizAttempt(
            student_id=student_id,
            quiz_id=quiz_id,
            score=score,
            passed=raw_score >= PASS_SCORE,
            attempt_number=latest.attempt_number + 1 if latest else 1,
            request_id=request_id,
            request_hash=fingerprint,
        )
        db.add(attempt)
        db.flush()
        db.add_all(
            [
                QuizAnswer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    selected_answer=selected.get(question.id),
                    is_correct=selected.get(question.id) == question.correct_answer,
                )
                for question in questions
            ]
        )
        if raw_score < REMEDIATION_SCORE:
            db.add(CheckpointRemediation(attempt_id=attempt.id))
        db.flush()

        result = _result(db, attempt)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        _context(db, quiz_id, student_id)
        existing = _existing(db, student_id, quiz_id, request_id)
        if existing is not None:
            return _replay(db, existing, fingerprint)
        raise HTTPException(
            status_code=409,
            detail="Concurrent submission; retry with the same request ID.",
        ) from None
    except Exception:
        db.rollback()
        raise


def attempt_history(
    db: Session,
    quiz_id: int,
    student_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[QuizAttemptResultResponse]:
    _context(db, quiz_id, student_id)
    attempts = db.scalars(
        select(QuizAttempt)
        .where(
            QuizAttempt.student_id == student_id,
            QuizAttempt.quiz_id == quiz_id,
        )
        .order_by(QuizAttempt.attempt_number.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_result(db, attempt) for attempt in attempts]


# ---------------------------------------------------------------------------
# Legacy compatibility wrappers
# Keep old callers working without duplicating grading or access rules.
# ---------------------------------------------------------------------------

def _assert_quiz_section_access(
    db: Session,
    *,
    student_id: int,
    section_id: int,
) -> None:
    section = quizzes_repo.get_section_by_id(db, section_id)
    if section is None:
        raise QuizNotFoundError("Section not found.")
    try:
        unlock_service.assert_section_unlocked(
            db,
            student_id=student_id,
            course_id=section.course_id,
            section_id=section.id,
        )
    except SectionLockedError as exc:
        raise QuizAccessDeniedError(str(exc)) from exc


def get_quiz_for_student(db: Session, *, section_id: int) -> dict:
    quiz = quizzes_repo.get_quiz_by_section(db, section_id)
    if quiz is None:
        raise QuizNotFoundError("Quiz not found for this section.")
    if not quiz.is_approved:
        raise QuizNotApprovedError("Quiz is not approved yet.")

    questions = quizzes_repo.get_questions_by_quiz(db, quiz.id)
    return {
        "id": quiz.id,
        "section_id": quiz.section_id,
        "title": quiz.title,
        "passing_score": max(MIN_PASSING_SCORE, quiz.passing_score),
        "questions": [
            {
                "id": question.id,
                "quiz_id": question.quiz_id,
                "question": question.question,
                "options": question.options_json,
                "position": question.position,
            }
            for question in questions
        ],
    }


def get_unlocked_quiz_for_student(
    db: Session,
    *,
    student_id: int,
    section_id: int,
) -> dict:
    _assert_quiz_section_access(
        db,
        student_id=student_id,
        section_id=section_id,
    )
    return get_quiz_for_student(db, section_id=section_id)


def submit_quiz(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
    submission: QuizSubmitRequest,
) -> dict:
    quiz = quizzes_repo.lock_quiz_for_submission(db, quiz_id=quiz_id)
    if quiz is None:
        raise QuizNotFoundError("Quiz not found.")
    if not quiz.is_approved:
        raise QuizNotApprovedError("Quiz is not approved yet.")

    _assert_quiz_section_access(
        db,
        student_id=student_id,
        section_id=quiz.section_id,
    )
    questions = quizzes_repo.get_questions_by_quiz(db, quiz_id)
    if not questions:
        raise InvalidSubmissionError("Cannot submit a quiz without questions.")

    answers_by_question_id: dict[int, str] = {}
    for answer in submission.answers:
        if answer.question_id in answers_by_question_id:
            raise InvalidSubmissionError(
                f"Multiple answers submitted for question {answer.question_id}."
            )
        answers_by_question_id[answer.question_id] = answer.selected_answer

    question_ids = {question.id for question in questions}
    unexpected_ids = set(answers_by_question_id) - question_ids
    if unexpected_ids:
        raise InvalidSubmissionError(
            "Submission contains questions that do not belong to this quiz."
        )

    correct_count = 0
    results: list[dict] = []
    answers_data: list[dict] = []
    for question in questions:
        selected_answer = answers_by_question_id.get(question.id, "")
        if selected_answer and selected_answer not in question.options_json:
            raise InvalidSubmissionError(
                f"Answer for question {question.id} must match one of its options."
            )
        is_correct = bool(selected_answer) and selected_answer == question.correct_answer
        if is_correct:
            correct_count += 1
        answers_data.append(
            {
                "question_id": question.id,
                "selected_answer": selected_answer or None,
                "is_correct": is_correct,
            }
        )
        results.append(
            {
                "id": question.id,
                "quiz_id": question.quiz_id,
                "question": question.question,
                "options": question.options_json,
                "selected_answer": selected_answer or None,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "explanation": question.explanation,
            }
        )

    score = Decimal(correct_count * 100) / Decimal(len(questions))
    passed = score >= max(PASS_SCORE, Decimal(str(quiz.passing_score)))
    attempt_number = quizzes_repo.count_user_attempts(
        db,
        student_id=student_id,
        quiz_id=quiz_id,
    ) + 1

    try:
        with quizzes_repo.submission_transaction(db):
            attempt = quizzes_repo.create_attempt(
                db,
                student_id=student_id,
                quiz_id=quiz_id,
                score=float(score),
                passed=passed,
                attempt_number=attempt_number,
            )
            quizzes_repo.save_attempt_answers(
                db,
                attempt_id=attempt.id,
                answers_data=answers_data,
            )
    except Exception:
        raise

    return {
        "id": attempt.id,
        "quiz_id": attempt.quiz_id,
        "student_id": attempt.student_id,
        "score": attempt.score,
        "passed": attempt.passed,
        "attempt_number": attempt.attempt_number,
        "created_at": attempt.created_at,
        "results": results,
    }


def get_student_quiz_history(
    db: Session,
    *,
    student_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    attempts = quizzes_repo.list_attempts_by_student_with_quiz_title(
        db,
        student_id=student_id,
        skip=skip,
        limit=limit,
    )
    return [
        {
            "id": attempt.id,
            "quiz_id": attempt.quiz_id,
            "quiz_title": quiz_title,
            "score": attempt.score,
            "passed": attempt.passed,
            "attempt_number": attempt.attempt_number,
            "created_at": attempt.created_at,
        }
        for attempt, quiz_title in attempts
    ]
