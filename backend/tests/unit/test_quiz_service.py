from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.quizzes import submit_quiz as submit_quiz_endpoint
from app.database import Base
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt
from app.models.section import Section
from app.models.user import User
from app.repositories import quizzes_repo
from app.schemas.quiz import (
    QuestionResponse,
    QuizAttemptResultResponse,
    QuizDetailResponse,
    QuizSubmitRequest,
)
from app.services import quiz_service


def _create_quiz(db_session, section_id: int, *, approved: bool = True) -> Quiz:
    quiz = Quiz(
        section_id=section_id,
        title="Checkpoint",
        passing_score=80.0,
        is_approved=approved,
    )
    db_session.add(quiz)
    db_session.flush()
    db_session.add(
        Question(
            quiz_id=quiz.id,
            question="Question?",
            options_json=["A", "B", "C", "D"],
            correct_answer="A",
            explanation="A is correct.",
            position=1,
        )
    )
    db_session.commit()
    return quiz


def _grant_access(db_session, student, course, section) -> Lesson:
    """Create the enrollment/progress required by the production checkpoint gate."""
    db_session.add(Enrollment(student_id=student.id, course_id=course.id))
    lesson = Lesson(
        section_id=section.id,
        title="Published lesson",
        position=1,
        status="PUBLISHED",
    )
    db_session.add(lesson)
    db_session.flush()
    db_session.add(LessonProgress(
        student_id=student.id,
        lesson_id=lesson.id,
        watched_seconds=1,
        completed=True,
    ))
    db_session.commit()
    return lesson


def test_quiz_get_and_attempt_responses_validate(db_session, quiz_course):
    student, course, sections = quiz_course
    quiz = _create_quiz(db_session, sections[0].id)
    lesson = _grant_access(db_session, student, course, sections[0])
    question = quizzes_repo.get_questions_by_quiz(db_session, quiz.id)[0]

    orm_question = QuestionResponse.model_validate(question)
    assert orm_question.options == ["A", "B", "C", "D"]
    assert "options" in orm_question.model_dump()
    assert "options_json" not in orm_question.model_dump()

    get_data = quiz_service.get_quiz_for_student(
        db_session,
        section_id=sections[0].id,
    )
    get_response = QuizDetailResponse.model_validate(get_data)
    get_question = get_response.model_dump()["questions"][0]
    assert get_question["options"] == ["A", "B", "C", "D"]
    assert "correct_answer" not in get_question
    assert "explanation" not in get_question
    assert get_response.is_approved is True
    assert get_response.created_at == quiz.created_at
    assert get_response.updated_at == quiz.updated_at

    post_data = quiz_service.submit_quiz(
        db_session,
        student_id=student.id,
        quiz_id=quiz.id,
        submission=QuizSubmitRequest(
            request_id=uuid4(),
            lesson_id=lesson.id,
            answers=[{"question_id": question.id, "selected_answer": "A"}]
        ),
    )
    post_response = QuizAttemptResultResponse.model_validate(post_data)
    result = post_response.model_dump()["answers"][0]
    assert result["selected_answer"] == "A"
    assert result["is_correct"] is True
    assert "correct_answer" not in post_response.model_dump_json()
    assert "explanation" not in post_response.model_dump_json()


def test_submit_locked_quiz_returns_403_without_attempt(
    db_session,
    quiz_course,
):
    student, course, sections = quiz_course
    _create_quiz(db_session, sections[0].id)
    _grant_access(db_session, student, course, sections[0])
    locked_quiz = _create_quiz(db_session, sections[1].id)
    question = quizzes_repo.get_questions_by_quiz(db_session, locked_quiz.id)[0]

    with pytest.raises(HTTPException) as error:
        submit_quiz_endpoint(
            quiz_id=locked_quiz.id,
            body=QuizSubmitRequest(
                request_id=uuid4(),
                answers=[{"question_id": question.id, "selected_answer": "A"}]
            ),
            db=db_session,
            current_user=student,
        )

    assert error.value.status_code == 403
    assert db_session.query(QuizAttempt).count() == 0


def test_quiz_submit_request_replays_without_exposing_answer_key(
    db_session,
    quiz_course,
):
    student, course, sections = quiz_course
    quiz = _create_quiz(db_session, sections[0].id)
    lesson = _grant_access(db_session, student, course, sections[0])
    question = quizzes_repo.get_questions_by_quiz(db_session, quiz.id)[0]
    request_id = uuid4()
    payload = QuizSubmitRequest(
        request_id=request_id,
        lesson_id=lesson.id,
        answers=[{"question_id": question.id, "selected_answer": "A"}],
    )

    first = quiz_service.submit_quiz(
        db_session, student_id=student.id, quiz_id=quiz.id,
        submission=payload,
    )
    replay = quiz_service.submit_quiz(
        db_session, student_id=student.id, quiz_id=quiz.id,
        submission=payload,
    )

    assert replay.id == first.id
    assert db_session.query(QuizAttempt).count() == 1
    public = replay.model_dump(mode="json")
    assert "correct_answer" not in str(public)
    assert "explanation" not in str(public)

    with pytest.raises(HTTPException) as conflict:
        quiz_service.submit_quiz(
            db_session, student_id=student.id, quiz_id=quiz.id,
            submission=QuizSubmitRequest(
                request_id=request_id,
                lesson_id=lesson.id,
                answers=[{
                    "question_id": question.id,
                    "selected_answer": "B",
                }],
            ),
        )
    assert conflict.value.status_code == 409


def test_failed_answer_persistence_rolls_back_passed_attempt(
    db_session,
    quiz_course,
    monkeypatch,
):
    student, course, sections = quiz_course
    quiz = _create_quiz(db_session, sections[0].id)
    lesson = _grant_access(db_session, student, course, sections[0])
    question = quizzes_repo.get_questions_by_quiz(db_session, quiz.id)[0]

    def fail_after_saving_answers(*args, **kwargs):
        raise RuntimeError("answer persistence failed")

    monkeypatch.setattr(
        quiz_service,
        "_result",
        fail_after_saving_answers,
    )

    with pytest.raises(RuntimeError, match="answer persistence failed"):
        quiz_service.submit_quiz(
            db_session,
            student_id=student.id,
            quiz_id=quiz.id,
            submission=QuizSubmitRequest(
                request_id=uuid4(),
                lesson_id=lesson.id,
                answers=[{"question_id": question.id, "selected_answer": "A"}]
            ),
        )

    assert db_session.query(QuizAttempt).count() == 0
    assert db_session.query(QuizAnswer).count() == 0


def test_history_maps_title_without_changing_response(db_session, quiz_course):
    student, _, sections = quiz_course
    quiz = _create_quiz(db_session, sections[0].id)
    attempt = QuizAttempt(
        student_id=student.id,
        quiz_id=quiz.id,
        score=100,
        passed=True,
        attempt_number=1,
    )
    db_session.add(attempt)
    db_session.commit()

    history = quiz_service.get_student_quiz_history(
        db_session,
        student_id=student.id,
    )

    assert history == [
        {
            "id": attempt.id,
            "quiz_id": quiz.id,
            "quiz_title": quiz.title,
            "score": 100,
            "passed": True,
            "attempt_number": 1,
            "created_at": attempt.created_at,
        }
    ]


def test_concurrent_retries_with_same_request_create_one_attempt(tmp_path):
    database_path = tmp_path / "concurrent-quiz.sqlite3"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    try:
        with session_factory() as setup_db:
            student = User(
                cognito_sub="concurrent-student",
                name="Student",
                email="concurrent@example.test",
                role="STUDENT",
            )
            setup_db.add(student)
            setup_db.flush()
            course = Course(
                instructor_id=student.id,
                title="Course",
                status="PUBLISHED",
            )
            setup_db.add(course)
            setup_db.flush()
            section = Section(
                course_id=course.id,
                title="First section",
                position=1,
            )
            setup_db.add(section)
            setup_db.flush()
            setup_db.add(Enrollment(
                student_id=student.id,
                course_id=course.id,
            ))
            lesson = Lesson(
                section_id=section.id,
                title="Published lesson",
                position=1,
                status="PUBLISHED",
            )
            setup_db.add(lesson)
            setup_db.flush()
            setup_db.add(LessonProgress(
                student_id=student.id,
                lesson_id=lesson.id,
                watched_seconds=1,
                completed=True,
            ))
            quiz = Quiz(
                section_id=section.id,
                title="Quiz",
                passing_score=80.0,
                is_approved=True,
            )
            setup_db.add(quiz)
            setup_db.flush()
            question = Question(
                quiz_id=quiz.id,
                question="Question?",
                options_json=["A", "B"],
                correct_answer="A",
                position=1,
            )
            setup_db.add(question)
            setup_db.commit()

            student_id = student.id
            quiz_id = quiz.id
            question_id = question.id
            lesson_id = lesson.id

        start_barrier = Barrier(2)
        request_id = uuid4()

        def submit_concurrently():
            with session_factory() as db:
                db.query(User.id).filter(User.id == student_id).first()
                start_barrier.wait(timeout=5)
                return quiz_service.submit_quiz(
                    db,
                    student_id=student_id,
                    quiz_id=quiz_id,
                    submission=QuizSubmitRequest(
                        request_id=request_id,
                        lesson_id=lesson_id,
                        answers=[
                            {
                                "question_id": question_id,
                                "selected_answer": "A",
                            }
                        ]
                    ),
                ).attempt_number

        with ThreadPoolExecutor(max_workers=2) as executor:
            attempt_numbers = list(
                executor.map(lambda _: submit_concurrently(), range(2))
            )

        assert attempt_numbers == [1, 1]
        with session_factory() as verify_db:
            persisted_numbers = [
                attempt_number
                for (attempt_number,) in verify_db.query(
                    QuizAttempt.attempt_number
                )
                .filter(
                    QuizAttempt.student_id == student_id,
                    QuizAttempt.quiz_id == quiz_id,
                )
                .all()
            ]
        assert persisted_numbers == [1]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
