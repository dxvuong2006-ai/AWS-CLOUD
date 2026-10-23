from sqlalchemy.orm import Session

from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt


def get_quiz_by_id(db: Session, quiz_id: int) -> Quiz | None:
    return db.query(Quiz).filter(Quiz.id == quiz_id).first()


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
    passing_score: float = 80.0,
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
    try:
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
    except Exception:
        db.rollback()
        raise
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
    try:
        db.add_all(answers)
        db.commit()
    except Exception:
        db.rollback()
        raise


def has_passed_quiz(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
) -> bool:
    return (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.passed.is_(True),
        )
        .first()
        is not None
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
