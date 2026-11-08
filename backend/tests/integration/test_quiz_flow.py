"""Kiểm thử luồng quiz, Tutor và mở khóa qua API."""

from fastapi.testclient import TestClient

from app.adapters.ai.mock_ai import MockAIAdapter
from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.user import User
from app.schemas.review import DraftApproval, DraftGeneration
from app.services import review_service, unlock_service


class FiveQuestionAI(MockAIAdapter):
    """Sinh năm câu hỏi cố định cho kiểm thử."""

    def generate_quiz(self, transcript, num_questions=5):
        """Trả đề đủ năm câu."""
        return {"questions": [
            {"question": f"Cloud question {i}?", "options": ["A", "B", "C", "D"],
             "correct_answer": "A", "explanation": "Cloud is useful."}
            for i in range(num_questions)
        ]}


def test_fail_tutor_retry_and_unlock(db_session, quiz_course):
    """Mô phỏng duyệt bài, thi trượt, ôn tập và thi lại đạt."""
    student, course, sections = quiz_course
    instructor = User(name="Teacher", email="flow@example.test",
                      role="INSTRUCTOR")
    db_session.add(instructor)
    db_session.flush()
    course.instructor_id = instructor.id
    db_session.add(Enrollment(student_id=student.id, course_id=course.id))
    lesson = Lesson(section_id=sections[0].id, title="Cloud", position=1,
                    status="DRAFT")
    db_session.add(lesson)
    db_session.commit()
    transcript = {"segments": [{"start": 12, "end": 25,
                                "text": "Cloud cung cấp máy chủ."}]}
    draft = review_service.generate_draft(
        db_session, lesson_id=lesson.id, instructor_id=instructor.id,
        payload=DraftGeneration(transcript="Cloud cung cấp máy chủ.",
                                num_questions=5),
        ai=FiveQuestionAI(), transcript_data=transcript,
    )
    review_service.approve_draft(
        db_session, lesson_id=lesson.id, instructor_id=instructor.id,
        payload=DraftApproval(expected_revision=draft.revision),
    )
    db_session.add(Lesson(section_id=sections[0].id, title="Second",
                          position=2, status="APPROVED",
                          transcript_json={"segments": [
                              {"start": 40, "end": 50,
                               "text": "Lambda xử lý sự kiện."}]}))
    db_session.commit()

    def override_db():
        """Tiêm session kiểm thử."""
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: student
    try:
        with TestClient(app) as client:
            response = client.get(f"/sections/{sections[0].id}/quiz")
            assert response.status_code == 200
            quiz = response.json()
            answers = [{"question_id": q["id"],
                        "selected_answer": "A" if i < 2 else "B"}
                       for i, q in enumerate(quiz["questions"])]
            result = client.post(f"/quizzes/{quiz['id']}/attempts",
                                 json={"answers": answers}).json()
            assert result["score"] == 40 and not result["passed"]
            assert not unlock_service.is_section_unlocked(
                db_session, student_id=student.id, course_id=course.id,
                section_id=sections[1].id)
            session = client.post("/tutor/sessions", json={
                "attempt_id": result["id"]}).json()
            assert "correct_answer" not in session["practice_questions"][0]
            chat = client.post(f"/tutor/sessions/{session['id']}/messages",
                               json={"message": "Cloud là gì?"}).json()
            assert "00:00:12" in chat["message"]
            other = client.post(f"/tutor/sessions/{session['id']}/messages",
                                json={"message": "Lambda là gì?"}).json()
            assert "00:00:40" in other["message"]
            path = f"/tutor/sessions/{session['id']}/practice-attempts"
            assert not client.post(path, json={"answers": ["B"] * 3}).json()[
                "remediation_completed"]
            assert client.post(path, json={"answers": ["A"] * 3}).json()[
                "remediation_completed"]
            for answer in answers:
                answer["selected_answer"] = "A"
            retry = client.post(f"/quizzes/{quiz['id']}/attempts",
                                json={"answers": answers}).json()
            assert retry["score"] == 100 and retry["passed"]
            assert unlock_service.is_section_unlocked(
                db_session, student_id=student.id, course_id=course.id,
                section_id=sections[1].id)
    finally:
        app.dependency_overrides.clear()
