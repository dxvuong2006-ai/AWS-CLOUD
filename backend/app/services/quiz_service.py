from sqlalchemy.orm import Session

from app.models.quiz import MIN_PASSING_SCORE
from app.repositories import quizzes_repo
from app.schemas.quiz import QuizSubmitRequest
from app.services import unlock_service
from app.services.unlock_service import SectionLockedError


class QuizNotFoundError(Exception):
    """Báo không tìm thấy bài trắc nghiệm hoặc chương học.

    Vai trò kiến trúc: Service.
    """

    pass


class QuizNotApprovedError(Exception):
    """Báo bài trắc nghiệm chưa được phê duyệt.

    Vai trò kiến trúc: Service.
    """

    pass


class QuizAccessDeniedError(Exception):
    """Báo học viên chưa đủ điều kiện tiến độ để vào đề.

    Vai trò kiến trúc: Service.
    """

    pass


class InvalidSubmissionError(Exception):
    """Báo dữ liệu nộp bài không hợp lệ để chấm điểm.

    Vai trò kiến trúc: Service.
    """

    pass


def _assert_quiz_section_access(
    db: Session,
    *,
    student_id: int,
    section_id: int,
) -> None:
    """Kiểm tra điều kiện tiến độ trước khi truy cập bài thi.

    Hàm kiểm tra tiến độ học; không thay thế phân quyền khóa học.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        section_id: Mã chương học cần xử lý.

    Returns:
        None nếu chương tồn tại và đã được mở khóa.

    Raises:
        QuizNotFoundError: Không tìm thấy chương của bài trắc nghiệm.
        QuizAccessDeniedError: Học viên chưa đạt điều kiện mở khóa.
    """
    section = quizzes_repo.get_section_by_id(db, section_id)
    if section is None:
        raise QuizNotFoundError("Section not found.")
    try:
        unlock_service.assert_section_unlocked(
            db,
            student_id=student_id,
            course_id=section.course_id,
            section_id=section.id,
        )
    except SectionLockedError as exc:
        raise QuizAccessDeniedError(str(exc)) from exc


def get_unlocked_quiz_for_student(
    db: Session,
    *,
    student_id: int,
    section_id: int,
) -> dict:
    """Lấy đề thi sau khi kiểm tra điều kiện mở khóa.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        section_id: Mã chương học cần xử lý.

    Returns:
        Đối tượng đề thi cho học viên, không có đáp án hoặc lời giải.

    Raises:
        QuizNotFoundError: Không tìm thấy chương hoặc bài thi.
        QuizAccessDeniedError: Chương học chưa được mở khóa.
        QuizNotApprovedError: Bài trắc nghiệm chưa được duyệt.
    """
    _assert_quiz_section_access(
        db,
        student_id=student_id,
        section_id=section_id,
    )
    return get_quiz_for_student(db, section_id=section_id)


def get_quiz_for_student(db: Session, *, section_id: int) -> dict:
    """Đọc đề thi đã duyệt và chỉ chọn các trường công khai.

    Bên gọi phải kiểm tra mở khóa trước khi phục vụ yêu cầu học viên.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        section_id: Mã chương học cần xử lý.

    Returns:
        Đối tượng đề thi dùng options, không có correct_answer/explanation.

    Raises:
        QuizNotFoundError: Chương học chưa có bài trắc nghiệm.
        QuizNotApprovedError: Bài trắc nghiệm chưa được duyệt.
    """
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
        "passing_score": max(MIN_PASSING_SCORE, quiz.passing_score),
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
    """Nộp bài và lưu lượt thi cùng câu trả lời theo cơ chế nguyên tử.

    Repository commit một lần khi xử lý hoàn tất; rollback nếu có lỗi.
    Ngưỡng đạt không thấp hơn 80 phần trăm và cấu hình của bài thi.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        quiz_id: Mã bài trắc nghiệm cần xử lý.
        submission: DTO chứa các câu trả lời do học viên gửi.

    Returns:
        Đối tượng kết quả có điểm, trạng thái đạt và chi tiết đáp án.

    Raises:
        QuizNotFoundError: Không tìm thấy bài thi hoặc chương học.
        QuizNotApprovedError: Bài thi chưa được duyệt.
        QuizAccessDeniedError: Chương học chưa được mở khóa.
        InvalidSubmissionError: Nội dung nộp bài không hợp lệ.
    """
    with quizzes_repo.submission_transaction(db):
        return _submit_quiz(
            db,
            student_id=student_id,
            quiz_id=quiz_id,
            submission=submission,
        )


def _submit_quiz(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
    submission: QuizSubmitRequest,
) -> dict:
    """Kiểm tra và chấm bài trong giao dịch nộp bài đang mở.

    Lấy khóa trước khi tính attempt_number. Attempt và answers dùng cùng
    Session; transaction bên ngoài chịu trách nhiệm commit/rollback.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        quiz_id: Mã bài trắc nghiệm cần xử lý.
        submission: DTO chứa các câu trả lời do học viên gửi.

    Returns:
        Đối tượng kết quả gồm lượt thi và đáp án sau khi nộp bài.

    Raises:
        QuizNotFoundError: Không tìm thấy bài thi hoặc chương học.
        QuizNotApprovedError: Bài trắc nghiệm chưa được duyệt.
        QuizAccessDeniedError: Chương học chưa được mở khóa.
        InvalidSubmissionError: Câu hỏi, lựa chọn hoặc đề thi không hợp lệ.
    """
    quiz = quizzes_repo.lock_quiz_for_submission(db, quiz_id=quiz_id)
    if quiz is None:
        raise QuizNotFoundError("Quiz not found.")
    if not quiz.is_approved:
        raise QuizNotApprovedError("Quiz is not approved yet.")

    _assert_quiz_section_access(
        db,
        student_id=student_id,
        section_id=quiz.section_id,
    )

    questions = quizzes_repo.get_questions_by_quiz(db, quiz_id)
    if not questions:
        raise InvalidSubmissionError("Cannot submit a quiz without questions.")

    answers_by_question_id: dict[int, str] = {}
    for answer in submission.answers:
        if answer.question_id in answers_by_question_id:
            raise InvalidSubmissionError(
                "Multiple answers submitted for question "
                f"{answer.question_id}."
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
        if selected_answer and selected_answer not in question.options_json:
            raise InvalidSubmissionError(
                f"Answer for question {question.id} "
                "must match one of its options."
            )
        is_correct = (
            bool(selected_answer)
            and selected_answer == question.correct_answer
        )
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
    passed = score >= max(MIN_PASSING_SCORE, quiz.passing_score)
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
    # Chụp giá trị đã flush trước khi commit làm hết hạn dữ liệu trong ORM.
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
    """Tổng hợp lịch sử lượt thi của học viên.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        skip: Số lượt thi bỏ qua khi phân trang.
        limit: Số lượt thi tối đa cần lấy.

    Returns:
        Danh sách kết quả lịch sử có tiêu đề quiz và thông tin chấm điểm.
    """
    attempts = quizzes_repo.list_attempts_by_student_with_quiz_title(
        db,
        student_id=student_id,
        skip=skip,
        limit=limit,
    )
    return [
        {
            "id": attempt.id,
            "quiz_id": attempt.quiz_id,
            "quiz_title": quiz_title,
            "score": attempt.score,
            "passed": attempt.passed,
            "attempt_number": attempt.attempt_number,
            "created_at": attempt.created_at,
        }
        for attempt, quiz_title in attempts
    ]
