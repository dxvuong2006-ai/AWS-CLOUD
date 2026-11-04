"""Kiểm thử Tutor và Analytics bằng SQLite."""

import pytest
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt
from app.services import tutor_service, analytics_service


@pytest.fixture
def learning_data(db_session, quiz_course):
    """Tạo bài học và một lần thi chưa đạt."""
    student, course, sections = quiz_course
    db_session.add(Enrollment(student_id=student.id, course_id=course.id))
    lesson = Lesson(section_id=sections[0].id, title="Cloud", position=1,
                    status="APPROVED", transcript_json={
                        "text": "Cloud cung cấp máy chủ. AWS cung cấp cloud."
                    })
    quiz = Quiz(section_id=sections[0].id, title="Cloud", is_approved=True)
    db_session.add_all([lesson, quiz])
    db_session.flush()
    question = Question(quiz_id=quiz.id, position=1, question="Cloud là gì?",
                        options_json=["máy chủ", "bánh"], correct_answer="máy chủ",
                        explanation="Cloud cung cấp máy chủ.")
    db_session.add(question)
    db_session.flush()
    attempt = QuizAttempt(student_id=student.id, quiz_id=quiz.id, score=0,
                          passed=False, attempt_number=1)
    db_session.add(attempt)
    db_session.flush()
    db_session.add(QuizAnswer(attempt_id=attempt.id, question_id=question.id,
                              selected_answer="bánh", is_correct=False))
    db_session.commit()
    return student, course, attempt


def test_tutor_end_to_end(db_session, learning_data):
    """Tạo phiên, trả lời và chỉ hoàn tất khi luyện tập đúng."""
    student, _, attempt = learning_data
    result = tutor_service.create_session(db_session, student.id, attempt.id)
    assert "correct_answer" not in result["practice_questions"][0]
    message = tutor_service.send_message(db_session, student.id,
                                         result["id"], "Cloud là gì?")
    assert "Cloud" in message["message"]
    first = tutor_service.submit_practice(db_session, student.id,
                                          result["id"], ["bánh"])
    assert not first["remediation_completed"]
    final = tutor_service.submit_practice(db_session, student.id,
                                          result["id"], ["máy chủ"])
    assert final["remediation_completed"]


def test_tutor_rejects_other_student(db_session, learning_data):
    """Không cho học viên khác dùng lượt thi."""
    _, _, attempt = learning_data
    with pytest.raises(tutor_service.TutorError) as exc:
        tutor_service.create_session(db_session, 9999, attempt.id)
    assert exc.value.code == 404


def test_analytics_counts(db_session, learning_data):
    """Tổng hợp điểm và câu trả lời sai của khóa học."""
    student, course, _ = learning_data
    result = analytics_service.get_course_analytics(db_session, course.id,
                                                     student.id)
    assert result["enrollment_count"] == 1
    assert result["attempt_count"] == 1
    assert result["failed_attempts"] == 1
    assert result["frequently_missed_questions"][0]["incorrect_count"] == 1
    assert analytics_service.get_course_analytics(db_session, course.id, 9999) is None



def test_tutor_and_analytics_endpoints(db_session, learning_data):
    """Kiểm tra route, quyền sở hữu và payload từ phía HTTP."""
    from fastapi.testclient import TestClient
    from app.dependencies import get_db, get_current_user
    from app.main import app
    from app.models.user import User

    student, course, attempt = learning_data
    instructor = User(name="Instructor", email="week4@example.test",
                      role="INSTRUCTOR")
    db_session.add(instructor)
    db_session.flush()
    course.instructor_id = instructor.id
    db_session.commit()
    actor = {"current": student}

    def database_override():
        """Cung cấp phiên SQLite thử nghiệm."""
        yield db_session

    def user_override():
        """Cung cấp người dùng hiện tại."""
        return actor["current"]

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = user_override
    try:
        with TestClient(app) as client:
            response = client.post("/tutor/sessions",
                                   json={"attempt_id": attempt.id})
            assert response.status_code == 201
            session_id = response.json()["id"]
            response = client.post(f"/tutor/sessions/{session_id}/messages",
                                   json={"message": "Cloud là gì?"})
            assert response.status_code == 200
            response = client.post(
                f"/tutor/sessions/{session_id}/practice-attempts",
                json={"answers": ["máy chủ"]},
            )
            assert response.json()["remediation_completed"]
            assert client.get(
                f"/instructor/courses/{course.id}/analytics"
            ).status_code == 403
            actor["current"] = instructor
            response = client.get(f"/instructor/courses/{course.id}/analytics")
            assert response.status_code == 200
            assert response.json()["failed_attempts"] == 1
    finally:
        app.dependency_overrides.clear()
