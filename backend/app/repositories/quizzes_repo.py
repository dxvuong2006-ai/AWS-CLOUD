from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Query, Session

from app.models.quiz import (
    MIN_PASSING_SCORE,
    Question,
    Quiz,
    QuizAnswer,
    QuizAttempt,
)
from app.models.section import Section


@contextmanager
def submission_transaction(db: Session) -> Iterator[None]:
    """Persist the locked quiz's attempt and answers as one unit of work."""
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_section_by_id(db: Session, section_id: int) -> Section | None:
    return db.query(Section).filter(Section.id == section_id).first()


def get_quiz_by_id(db: Session, quiz_id: int) -> Quiz | None:
    return db.query(Quiz).filter(Quiz.id == quiz_id).first()


def lock_quiz_for_submission(db: Session, *, quiz_id: int) -> Quiz | None:
    dialect = db.get_bind().dialect.name
    quiz_query = db.query(Quiz).filter(Quiz.id == quiz_id)

    if dialect == "postgresql":
        return quiz_query.with_for_update().populate_existing().first()

    if dialect == "sqlite":
        # SQLite ignores SELECT FOR UPDATE; a no-op write serializes writers.
        updated_rows = quiz_query.update(
            {Quiz.id: Quiz.id},
            synchronize_session=False,
        )
        if not updated_rows:
            return None
        db.expire_all()
        return get_quiz_by_id(db, quiz_id)

    raise RuntimeError(
        f"Quiz submission locking is not configured for {dialect}."
    )


def get_quiz_by_section(db: Session, section_id: int) -> Quiz | None:
    return db.query(Quiz).filter(Quiz.section_id == section_id).first()


def get_questions_by_quiz(db: Session, quiz_id: int) -> list[Question]:
    return (
        db.query(Question)
        .filter(Question.quiz_id == quiz_id)
        .order_by(Question.position.asc())
        .all()
    )


def get_question_by_id(db: Session, question_id: int) -> Question | None:
    return db.query(Question).filter(Question.id == question_id).first()


def create_quiz(
    db: Session,
    *,
    section_id: int,
    title: str,
    passing_score: float = MIN_PASSING_SCORE,
    is_approved: bool = False,
) -> Quiz:
    quiz = Quiz(
        section_id=section_id,
        title=title,
        passing_score=passing_score,
        is_approved=is_approved,
    )
    try:
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
    except Exception:
        db.rollback()
        raise
    return quiz


def create_question(
    db: Session,
    *,
    quiz_id: int,
    question: str,
    options_json: list[str],
    correct_answer: str,
    explanation: str | None = None,
    position: int = 1,
) -> Question:
    new_question = Question(
        quiz_id=quiz_id,
        question=question,
        options_json=options_json,
        correct_answer=correct_answer,
        explanation=explanation,
        position=position,
    )
    try:
        db.add(new_question)
        db.commit()
        db.refresh(new_question)
    except Exception:
        db.rollback()
        raise
    return new_question


def count_user_attempts(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
) -> int:
    return (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.quiz_id == quiz_id,
        )
        .count()
    )


def create_attempt(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
    score: float,
    passed: bool,
    attempt_number: int,
) -> QuizAttempt:
    attempt = QuizAttempt(
        student_id=student_id,
        quiz_id=quiz_id,
        score=score,
        passed=passed,
        attempt_number=attempt_number,
    )
    db.add(attempt)
    db.flush()
    return attempt


def save_attempt_answers(
    db: Session,
    *,
    attempt_id: int,
    answers_data: list[dict],
) -> None:
    answers = [
        QuizAnswer(
            attempt_id=attempt_id,
            question_id=answer["question_id"],
            selected_answer=answer["selected_answer"],
            is_correct=answer["is_correct"],
        )
        for answer in answers_data
    ]
    db.add_all(answers)


def has_passed_quiz(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
) -> bool:
    return (
        _passed_attempts_query(db, student_id=student_id)
        .filter(QuizAttempt.quiz_id == quiz_id)
        .first()
        is not None
    )


def _passed_attempts_query(
    db: Session, *, student_id: int
) -> Query[QuizAttempt]:
    return (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.passed.is_(True),
            QuizAttempt.score >= MIN_PASSING_SCORE,
        )
    )


def list_section_quiz_progress(
    db: Session,
    *,
    student_id: int,
    course_id: int,
) -> list[tuple[int, bool]]:
    """Allow sections without quizzes; require a passing attempt for each quiz."""
    passed_attempt = (
        _passed_attempts_query(db, student_id=student_id)
        .filter(QuizAttempt.quiz_id == Quiz.id)
        .exists()
    )
    unmet_quiz = (
        db.query(Quiz.id)
        .filter(
            Quiz.section_id == Section.id,
            ~passed_attempt,
        )
        .exists()
    )
    return (
        db.query(Section.id, (~unmet_quiz).label("requirements_met"))
        .filter(Section.course_id == course_id)
        .order_by(Section.position.asc(), Section.id.asc())
        .all()
    )


def list_attempts_by_student(
    db: Session,
    *,
    student_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[QuizAttempt]:
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.student_id == student_id)
        .order_by(QuizAttempt.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_attempts_by_student_with_quiz_title(
    db: Session,
    *,
    student_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[tuple[QuizAttempt, str | None]]:
    return (
        db.query(QuizAttempt, Quiz.title)
        .outerjoin(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .filter(QuizAttempt.student_id == student_id)
        .order_by(QuizAttempt.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
