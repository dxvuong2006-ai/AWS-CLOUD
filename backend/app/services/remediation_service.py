"""Server-owned three-step remediation, resumable across page reloads."""
import math
import random
from copy import deepcopy
from fastapi import HTTPException
from app.models.tutor import TutorSession
from app.models.quiz import Quiz, QuizAttempt, CheckpointRemediation
from app.models.section import Section
from app.repositories import tutor_repo
from app.services import tutor_service


def owned(db, student_id, session_id):
    session = tutor_repo.get_session(db, session_id, student_id, lock=True)
    if session is None or not session.workflow_state:
        raise HTTPException(404, "Không tìm thấy phiên ôn tập.")
    return session


def public(db, session):
    state = session.workflow_state
    lesson = tutor_repo.get_lesson(db, session.lesson_id)
    section = db.get(Section, lesson.section_id)
    attempt = db.get(QuizAttempt, session.attempt_id)
    return {
        "id": session.id, "attempt_id": session.attempt_id,
        "quiz_id": attempt.quiz_id, "course_id": section.course_id,
        "section_id": section.id, "section_title": section.title,
        "lesson_id": lesson.id, "lesson_title": lesson.title,
        "errors": state["errors"], "seen_errors": state["seen_errors"],
        "cards": state["cards"], "reviewed_cards": state["reviewed_cards"],
        "explanation_completed": len(state["seen_errors"]) == len(state["errors"]),
        "review_completed": bool(state["cards"]) and len(state["reviewed_cards"]) == len(state["cards"]),
        "practice_questions": [{"question": q["question"], "options": q["options"]}
                               for q in session.practice_questions],
        "practice_source": state["practice_source"],
        "result": state.get("result"),
        "remediation_completed": session.remediation_completed,
    }


def start(db, student_id, attempt_id, regenerate=False):
    context = tutor_repo.attempt_context(db, attempt_id, student_id)
    if not context:
        raise HTTPException(404, "Không tìm thấy lượt làm của bạn.")
    attempt, lesson, questions = context
    if attempt.passed:
        raise HTTPException(409, "Checkpoint này đã đạt.")
    # Serialize starts for one attempt, preventing duplicate sessions on retries.
    db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).with_for_update().first()
    existing = db.query(TutorSession).filter(
        TutorSession.student_id == student_id, TutorSession.attempt_id == attempt_id,
        TutorSession.workflow_state.isnot(None)).order_by(TutorSession.id.desc()).first()
    if existing and (not regenerate or existing.remediation_completed):
        return public(db, existing)
    if regenerate and (not existing or not existing.workflow_state.get("result")):
        raise HTTPException(409, "Hãy nộp bộ luyện tập hiện tại trước.")
    try:
        created = tutor_service.create_session(db, student_id, attempt_id, defer_commit=True)
    except tutor_service.TutorError as exc:
        raise HTTPException(exc.code, str(exc)) from exc
    session = db.get(TutorSession, created["id"])
    wrong = [(q, a) for q, a in questions if a is None or not a.is_correct]
    excerpt = tutor_service._transcript(lesson).strip()[:1200]
    errors = [{"id": str(q.id), "concept": q.topic or q.question,
               "question": q.question, "selected": a.selected_answer if a else None,
               "misconception": "Bạn chưa trả lời đúng câu hỏi: " + q.question,
               "explanation": q.explanation or created["explanation"],
               "example": excerpt} for q, a in wrong]
    cards = [{"id": str(q.id), "front": q.topic or q.question,
              "back": q.explanation or created["explanation"]} for q, _ in wrong]
    practice = list(session.practice_questions)
    # Grounded fallback when only one misconception is available.
    if len(practice) < 2:
        answer = wrong[0][0].explanation or excerpt
        practice.append({"question": "Chọn phát biểu phù hợp với nội dung vừa ôn.",
                         "options": [answer, "Không có thông tin nào liên quan trong bài giảng."],
                         "correct_answer": answer, "explanation": answer})
    random.SystemRandom().shuffle(practice)
    practice = practice[:3]
    for question in practice:
        random.SystemRandom().shuffle(question["options"])
    session.practice_questions = deepcopy(practice)
    previous = existing.workflow_state if existing else {}
    # Existing AI adapter explicitly falls back to source questions.
    source = "lesson" if created["explanation"].startswith("Hãy xem lại") else "ai"
    session.workflow_state = {"errors": errors, "cards": cards,
        "seen_errors": previous.get("seen_errors", []),
        "reviewed_cards": previous.get("reviewed_cards", []),
        "practice_source": source}
    db.commit()
    return public(db, session)


def advance(db, student_id, session_id, kind, item_id):
    session = owned(db, student_id, session_id)
    state = deepcopy(session.workflow_state)
    collection, seen = ("errors", "seen_errors") if kind == "explanation" else ("cards", "reviewed_cards")
    if str(item_id) not in {row["id"] for row in state[collection]}:
        raise HTTPException(422, "Nội dung không thuộc phiên ôn tập.")
    if kind == "card" and len(state["seen_errors"]) != len(state["errors"]):
        raise HTTPException(409, "Cần xem hết giải thích trước khi ôn thẻ.")
    state[seen] = list(dict.fromkeys([*state[seen], str(item_id)]))
    session.workflow_state = state
    db.commit()
    return public(db, session)


def submit(db, student_id, session_id, answers):
    session = owned(db, student_id, session_id)
    state = deepcopy(session.workflow_state)
    if state.get("result"):
        return public(db, session)  # Idempotent result; no repeated answer probing.
    if (len(state["seen_errors"]) != len(state["errors"]) or
            not state["cards"] or len(state["reviewed_cards"]) != len(state["cards"])):
        raise HTTPException(409, "Hoàn thành giải thích và ôn lại bài trước khi luyện tập.")
    questions = session.practice_questions
    if len(questions) not in (2, 3) or len(answers) != len(questions) or any(
        answer not in q["options"] for answer, q in zip(answers, questions)):
        raise HTTPException(422, "Chọn một đáp án hợp lệ cho mỗi câu.")
    rows = [{"question": q["question"], "selected": a,
             "correct_answer": q["correct_answer"], "explanation": q.get("explanation", ""),
             "is_correct": a == q["correct_answer"]} for a, q in zip(answers, questions)]
    correct = sum(row["is_correct"] for row in rows)
    passed = correct >= math.ceil(len(questions) * 2 / 3)
    state["result"] = {"correct": correct, "total": len(questions), "passed": passed, "questions": rows}
    session.workflow_state = state
    session.remediation_completed = passed
    if passed:
        # Lock shared attempt before upserting the single trusted eligibility row.
        db.query(QuizAttempt).filter(QuizAttempt.id == session.attempt_id).with_for_update().first()
        review = db.get(CheckpointRemediation, session.attempt_id)
        if review is None:
            review = CheckpointRemediation(attempt_id=session.attempt_id)
            db.add(review)
        review.explanation_completed = True
        review.review_completed = True
        review.practice_total = len(questions)
        review.practice_correct = correct
    db.commit()
    return public(db, session)
