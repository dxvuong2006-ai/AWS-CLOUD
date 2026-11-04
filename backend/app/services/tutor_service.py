"""Điều phối phiên ôn tập và hội thoại dựa trên bài giảng."""

import os
import re
from ai_pipeline.processors.build_tutor_context import build_tutor_context
from app.models.tutor import TutorSession
from app.repositories import tutor_repo


class TutorError(Exception):
    """Lỗi nghiệp vụ Tutor có mã HTTP tương ứng."""

    def __init__(self, code, message):
        """Lưu mã lỗi và thông báo."""
        super().__init__(message)
        self.code = code


def _transcript(lesson):
    """Lấy văn bản transcript từ bài học đã duyệt."""
    data = lesson.transcript_json
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return data.get("full_text") or data.get("text") or " ".join(
            str(item.get("text", "")) for item in data.get("segments", [])
            if isinstance(item, dict))
    return ""


def _public(session):
    """Ẩn đáp án khi trả câu luyện tập cho học viên."""
    return {"id": session.id, "lesson_id": session.lesson_id,
            "attempt_id": session.attempt_id,
            "remediation_completed": session.remediation_completed,
            "practice_questions": [
                {"question": q["question"], "options": q["options"]}
                for q in session.practice_questions]}


def create_session(db, student_id, attempt_id, ai_client=None):
    """Tạo phiên cho lượt thi chưa đạt của học viên."""
    row = tutor_repo.attempt_context(db, attempt_id, student_id)
    if row is None:
        raise TutorError(404, "Attempt not found.")
    attempt, lesson, questions = row
    if attempt.passed:
        raise TutorError(409, "Attempt already passed.")
    if lesson is None or not _transcript(lesson).strip():
        raise TutorError(409, "Approved lesson transcript is unavailable.")
    incorrect = [
        {"question": question.question, "options": question.options_json,
         "correct_answer": question.correct_answer,
         "explanation": question.explanation or "Hãy xem lại bài giảng."}
        for question, answer in questions
        if answer is None or not answer.is_correct
    ]
    if not incorrect:
        raise TutorError(409, "No incorrect questions found.")
    if ai_client is None and os.getenv("TUTOR_USE_BEDROCK", "").lower() == "true":
        from ai_pipeline.processors._common import AIClientError
        from app.adapters.ai.bedrock_ai import AWS_FAILURES, BedrockAIAdapter

        adapter = BedrockAIAdapter()

        def ai_client(prompt):
            """Gọi Bedrock và chuyển lỗi AWS sang lỗi pipeline có dự phòng."""
            try:
                return adapter._invoke(prompt)
            except AWS_FAILURES as exc:
                raise AIClientError("Bedrock unavailable.") from exc

    result = build_tutor_context(_transcript(lesson), incorrect, ai_client)
    session = TutorSession(student_id=student_id, lesson_id=lesson.id,
                           attempt_id=attempt_id,
                           practice_questions=result["practice_questions"],
                           remediation_completed=False)
    tutor_repo.save_session(db, session, result["explanation"])
    return {**_public(session), "explanation": result["explanation"]}


def send_message(db, student_id, session_id, message):
    """Trả trích đoạn bài giảng có liên quan đến câu hỏi."""
    session = tutor_repo.get_session(db, session_id, student_id)
    if session is None:
        raise TutorError(404, "Tutor session not found.")
    lesson = tutor_repo.get_lesson(db, session.lesson_id)
    if lesson is None or lesson.status not in ("APPROVED", "PUBLISHED"):
        raise TutorError(403, "Lesson is unavailable.")
    transcript = _transcript(lesson)
    words = {word.casefold() for word in re.findall(r"\w+", message)
             if len(word) > 3}
    sentences = re.split(r"(?<=[.!?])\s+|\n+", transcript)
    matches = [line.strip() for line in sentences if words & {
        word.casefold() for word in re.findall(r"\w+", line)}]
    answer = ("Theo bài giảng: " + " ".join(matches[:2]) if matches else
              "Không tìm thấy thông tin liên quan trong bài giảng.")
    tutor_repo.save_messages(db, session.id, message, answer)
    return {"message": answer}


def submit_practice(db, student_id, session_id, answers):
    """Chấm đủ câu luyện tập và chỉ hoàn thành khi trả lời đúng tất cả."""
    session = tutor_repo.get_session(db, session_id, student_id, lock=True)
    if session is None:
        raise TutorError(404, "Tutor session not found.")
    questions = session.practice_questions
    if not questions or len(answers) != len(questions):
        raise TutorError(422, "Submit one answer per practice question.")
    if any(answer not in question["options"]
           for answer, question in zip(answers, questions)):
        raise TutorError(422, "Answer must match an option.")
    correct = sum(answer == question["correct_answer"]
                  for answer, question in zip(answers, questions))
    passed = correct == len(questions)
    if passed:
        tutor_repo.complete(db, session)
    return {"correct": correct, "total": len(questions),
            "remediation_completed": session.remediation_completed}
