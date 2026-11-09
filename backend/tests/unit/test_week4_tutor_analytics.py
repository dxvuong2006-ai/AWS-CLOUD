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
                    status="PUBLISHED", transcript_json={
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
    assert exc.value.code == 403


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


def test_idor_attempt_and_session_endpoints(db_session, learning_data):
    """Học viên khác nhận 403 với lượt thi và phiên không thuộc mình."""
    from fastapi.testclient import TestClient
    from app.dependencies import get_current_user, get_db
    from app.main import app
    from app.models.user import User

    student, course, attempt = learning_data
    other = User(name="Other student", email="other-week4@example.test",
                 role="STUDENT")
    db_session.add(other)
    db_session.flush()
    db_session.add(Enrollment(student_id=other.id, course_id=course.id))
    db_session.commit()
    session = tutor_service.create_session(db_session, student.id, attempt.id)

    def database_override():
        """Cung cấp session SQLite."""
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: other
    try:
        with TestClient(app) as client:
            assert client.post("/tutor/sessions", json={
                "attempt_id": attempt.id,
            }).status_code == 403
            url = f"/tutor/sessions/{session['id']}"
            assert client.post(url + "/messages", json={
                "message": "Cloud là gì?",
            }).status_code == 403
            assert client.post(url + "/practice-attempts", json={
                "answers": ["máy chủ"],
            }).status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_analytics_denies_non_owner_instructor(db_session, learning_data):
    """Giảng viên khác không xem được thống kê khóa học."""
    from fastapi.testclient import TestClient
    from app.dependencies import get_current_user, get_db
    from app.main import app
    from app.models.user import User

    _, course, _ = learning_data
    other = User(name="Other instructor", email="other-inst@example.test",
                 role="INSTRUCTOR")
    db_session.add(other)
    db_session.commit()

    def database_override():
        """Cung cấp session SQLite."""
        yield db_session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: other
    try:
        with TestClient(app) as client:
            assert client.get(
                f"/instructor/courses/{course.id}/analytics"
            ).status_code in (403, 404)
    finally:
        app.dependency_overrides.clear()


def test_timestamp_grounding_and_off_topic(db_session, learning_data):
    """Trích dẫn đúng mốc của segment, từ chối nội dung ngoài bài."""
    student, _, attempt = learning_data
    lesson = db_session.query(Lesson).filter_by(title="Cloud").one()
    lesson.transcript_json = {"segments": [
        {"start": 12, "end": 25, "text": "Cloud cung cấp máy chủ."},
        {"start": 28, "end": 35, "text": "AWS là nhà cung cấp."},
    ]}
    db_session.commit()
    session = tutor_service.create_session(db_session, student.id, attempt.id)
    result = tutor_service.send_message(
        db_session, student.id, session["id"], "Cloud cung cấp gì?")
    assert "[00:00:12 - 00:00:25]" in result["message"]
    result = tutor_service.send_message(
        db_session, student.id, session["id"], "khủng long tuyệt chủng?")
    assert "Không tìm thấy" in result["message"]


def test_weak_concepts_rate_and_topic(db_session, learning_data):
    """Tính tỷ lệ sai theo tổng câu trả lời và trả chủ đề."""
    student, course, attempt = learning_data
    question = db_session.query(Question).one()
    question.topic = "Cloud computing"
    another = QuizAttempt(student_id=student.id, quiz_id=attempt.quiz_id,
                          score=100, passed=True, attempt_number=2)
    db_session.add(another)
    db_session.flush()
    db_session.add(QuizAnswer(attempt_id=another.id, question_id=question.id,
                              selected_answer="máy chủ", is_correct=True))
    db_session.commit()
    result = analytics_service.get_course_analytics(db_session, course.id,
                                                     student.id)
    weak = result["weak_concepts"][0]
    assert weak["topic"] == "Cloud computing"
    assert weak["incorrect_count"] == 1
    assert weak["answer_count"] == 2
    assert weak["failure_rate"] == 50.0


def test_remediate_question_offline_and_check_owner(db_session, learning_data, monkeypatch):
    """Tutor xử lý câu sai offline và không lộ đáp án luyện tập."""
    from botocore.exceptions import NoCredentialsError
    from app.adapters.ai.bedrock_ai import BedrockAIAdapter
    from app.schemas.tutor import QuestionRemediationRequest

    student, _, attempt = learning_data
    lesson = db_session.query(Lesson).filter_by(title="Cloud").one()
    question = db_session.query(Question).one()
    payload = QuestionRemediationRequest(
        attempt_id=attempt.id, lesson_id=lesson.id,
        question_id=question.id, selected_option="bánh",
    )
    def offline(*args, **kwargs):
        """Giả lập lỗi credentials AWS."""
        raise NoCredentialsError()
    monkeypatch.setattr(BedrockAIAdapter, "_invoke", offline)
    result = tutor_service.remediate_question(db_session, student.id, payload)
    assert "bánh" in result["explanation"]
    assert "correct_answer" not in result["practice_question"]
    with pytest.raises(tutor_service.TutorError) as exc:
        tutor_service.remediate_question(db_session, 99999, payload)
    assert exc.value.code == 403



def test_remediate_question_ai_success(db_session, learning_data):
    """Lời giải AI và bài luyện tập vẫn ẩn đáp án."""
    import json
    from app.schemas.tutor import QuestionRemediationRequest

    student, _, attempt = learning_data
    lesson = db_session.query(Lesson).filter_by(title="Cloud").one()
    question = db_session.query(Question).one()
    payload = QuestionRemediationRequest(
        attempt_id=attempt.id, lesson_id=lesson.id,
        question_id=question.id, selected_option="bánh",
    )
    answer = json.dumps({
        "explanation": "Bánh không phải dịch vụ tính toán.",
        "practice_questions": [{"question": "Dịch vụ nào?",
                                "options": ["Cloud", "Bánh"],
                                "correct_answer": "Cloud",
                                "explanation": "Cloud cung cấp tài nguyên."}],
    })
    result = tutor_service.remediate_question(
        db_session, student.id, payload, ai_client=lambda prompt: answer,
    )
    assert result["explanation"] == "Bánh không phải dịch vụ tính toán."
    assert result["practice_question"]["options"] == ["Cloud", "Bánh"]
    assert "correct_answer" not in result["practice_question"]
