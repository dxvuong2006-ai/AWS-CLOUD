from sqlalchemy.orm import Session

from app.repositories import quizzes_repo
from app.schemas.quiz import QuizSubmitRequest


class QuizNotFoundError(Exception):
    pass


class QuizNotApprovedError(Exception):
    pass


class QuizAccessDeniedError(Exception):
    pass


class InvalidSubmissionError(Exception):
    pass


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
        "passing_score": quiz.passing_score,
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


def submit_quiz(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
    submission: QuizSubmitRequest,
) -> dict:
    quiz = quizzes_repo.get_quiz_by_id(db, quiz_id)
    if quiz is None:
        raise QuizNotFoundError("Quiz not found.")
    if not quiz.is_approved:
        raise QuizNotApprovedError("Quiz is not approved yet.")

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
    unexpected_question_ids = set(answers_by_question_id) - question_ids
    if unexpected_question_ids:
        raise InvalidSubmissionError(
            "Submission contains questions that do not belong to this quiz."
        )

    correct_count = 0
    results: list[dict] = []
    answers_data: list[dict] = []
    for question in questions:
        selected_answer = answers_by_question_id.get(question.id, "")
        is_correct = selected_answer == question.correct_answer
        if is_correct:
            correct_count += 1

        answers_data.append(
            {
                "question_id": question.id,
                "selected_answer": selected_answer,
                "is_correct": is_correct,
            }
        )
        results.append(
            {
                "id": question.id,
                "quiz_id": question.quiz_id,
                "question": question.question,
                "options": question.options_json,
                "selected_answer": selected_answer,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "explanation": question.explanation,
            }
        )

    score = (correct_count / len(questions)) * 100
    passed = score >= quiz.passing_score
    attempt_number = (
        quizzes_repo.count_user_attempts(
            db,
            student_id=student_id,
            quiz_id=quiz_id,
        )
        + 1
    )
    attempt = quizzes_repo.create_attempt(
        db,
        student_id=student_id,
        quiz_id=quiz_id,
        score=score,
        passed=passed,
        attempt_number=attempt_number,
    )
    quizzes_repo.save_attempt_answers(
        db,
        attempt_id=attempt.id,
        answers_data=answers_data,
    )

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
    attempts = quizzes_repo.list_attempts_by_student(
        db,
        student_id=student_id,
        skip=skip,
        limit=limit,
    )
    history: list[dict] = []
    for attempt in attempts:
        quiz = quizzes_repo.get_quiz_by_id(db, attempt.quiz_id)
        history.append(
            {
                "id": attempt.id,
                "quiz_id": attempt.quiz_id,
                "quiz_title": quiz.title if quiz is not None else None,
                "score": attempt.score,
                "passed": attempt.passed,
                "attempt_number": attempt.attempt_number,
                "created_at": attempt.created_at,
            }
        )
    return history
