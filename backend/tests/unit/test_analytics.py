"""Kiểm thử thống kê quiz và quyền truy cập."""

from fastapi.testclient import TestClient
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt
from app.models.user import User


def test_quiz_analytics_scoped_to_instructor(db_session, quiz_course):
    """Kiểm tra điểm, câu sai và chặn giảng viên không sở hữu."""
    student, course, sections = quiz_course
    teacher = User(name="Teacher", email="stats-owner@example.test", role="INSTRUCTOR")
    other = User(name="Other", email="stats-other@example.test", role="INSTRUCTOR")
    db_session.add_all([teacher, other])
    db_session.flush()
    course.instructor_id = teacher.id
    quiz = Quiz(section_id=sections[0].id, title="Quiz")
    db_session.add(quiz)
    db_session.flush()
    q = Question(quiz_id=quiz.id, question="Question?", options_json=["A", "B"],
                 correct_answer="A", position=1)
    db_session.add(q)
    db_session.flush()
    attempt = QuizAttempt(student_id=student.id, quiz_id=quiz.id, score=0,
                          passed=False, attempt_number=1)
    db_session.add(attempt)
    db_session.flush()
    db_session.add(QuizAnswer(attempt_id=attempt.id, question_id=q.id,
                              selected_answer="B", is_correct=False))
    db_session.commit()
    actor = {"user": teacher}

    def override_db():
        """Cấp session thử nghiệm."""
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: actor["user"]
    try:
        with TestClient(app) as client:
            response = client.get(f"/analytics/quizzes/{quiz.id}")
            assert response.status_code == 200
            assert response.json()["attempt_count"] == 1
            assert response.json()["average_score"] == 0
            assert response.json()["pass_rate"] == 0
            assert response.json()["frequently_missed_questions"][0]["incorrect_count"] == 1
            actor["user"] = other
            assert client.get(f"/analytics/quizzes/{quiz.id}").status_code == 404
            actor["user"] = student
            assert client.get(f"/analytics/quizzes/{quiz.id}").status_code == 403
    finally:
        app.dependency_overrides.clear()
