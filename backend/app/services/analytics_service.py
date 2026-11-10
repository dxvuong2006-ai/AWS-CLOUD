"""Tính chỉ số học tập dành cho giảng viên."""


from app.repositories import analytics_repo, tutor_repo


def get_course_analytics(db, course_id, instructor_id):
    """Kiểm tra quyền sở hữu và tổng hợp thống kê khóa học."""
    if analytics_repo.course_for_owner(db, course_id, instructor_id) is None:
        return None
    enrolled, attempts, errors, lessons, completed = (
        analytics_repo.course_metrics(db, course_id))
    total, passed, average = attempts
    passed = int(passed or 0)
    total = int(total or 0)
    opportunities = enrolled * lessons
    rows = tutor_repo.question_failure_rates(db, course_id)
    weak = sorted(
        ({"question_id": row.id, "question": row.question,
          "topic": row.topic, "incorrect_count": row.incorrect_count,
          "answer_count": row.answer_count,
          "failure_rate": round(100 * row.incorrect_count / row.answer_count, 2)}
         for row in rows if row.incorrect_count),
        key=lambda item: (-item["failure_rate"], -item["incorrect_count"],
                          item["question_id"]),
    )[:10]
    return {
        "weak_concepts": weak,
        "course_id": course_id, "enrollment_count": enrolled,
        "attempt_count": total, "passed_attempts": passed,
        "failed_attempts": total - passed,
        "pass_rate": round(100 * passed / total, 2) if total else 0.0,
        "average_score": float(average) if average is not None else None,
        "completion_rate": round(100 * completed / opportunities, 2)
        if opportunities else 0.0,
        "frequently_missed_questions": [
            {"question_id": row.id, "question": row.question,
             "incorrect_count": row.incorrect_count} for row in errors],
    }



def get_quiz_analytics(db, quiz_id, instructor_id):
    """Tổng hợp lượt thi của quiz thuộc khóa học giảng viên."""
    from sqlalchemy import Integer, func
    from app.models.quiz import Question, Quiz, QuizAnswer, QuizAttempt
    from app.repositories import quizzes_repo

    quiz = quizzes_repo.get_quiz_by_id(db, quiz_id)
    if quiz is None:
        return None
    section = quizzes_repo.get_section_by_id(db, quiz.section_id)
    if section is None or analytics_repo.course_for_owner(
        db, section.course_id, instructor_id
    ) is None:
        return None
    total, passed, average = (
        db.query(func.count(QuizAttempt.id),
                 func.sum(QuizAttempt.passed.cast(Integer)),
                 func.avg(QuizAttempt.score))
        .filter(QuizAttempt.quiz_id == quiz_id).one()
    )
    missed = (
        db.query(Question.id, Question.question,
                 func.count(QuizAnswer.id).label("incorrect_count"))
        .join(QuizAnswer, QuizAnswer.question_id == Question.id)
        .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
        .filter(Question.quiz_id == quiz_id, QuizAttempt.quiz_id == quiz_id,
                QuizAnswer.is_correct.is_(False))
        .group_by(Question.id, Question.question)
        .order_by(func.count(QuizAnswer.id).desc(), Question.id).limit(10).all()
    )
    return {"quiz_id": quiz_id, "attempt_count": total,
            "average_score": float(average) if average is not None else None,
            "pass_rate": round(100 * int(passed or 0) / total, 2) if total else 0.0,
            "frequently_missed_questions": [
                {"question_id": row.id, "question": row.question,
                 "incorrect_count": row.incorrect_count} for row in missed]}
