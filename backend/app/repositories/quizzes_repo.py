from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Query, Session

from app.models.quiz import (
    MIN_PASSING_SCORE,
    Question,
    Quiz,
    QuizAnswer,
    QuizAttempt,
)
from app.models.section import Section


@contextmanager
def submission_transaction(db: Session) -> Iterator[None]:
    """Bao trọn việc lưu lượt thi và câu trả lời trong một giao dịch.

    Commit một lần sau khi bên gọi hoàn tất. Nếu có lỗi, rollback trên cùng
    Session; không tự đóng Session do dependency quản lý.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.

    Yields:
        None: Phạm vi xử lý dùng chung giao dịch của Session.

    Raises:
        Exception: Lỗi trong phạm vi giao dịch được rollback rồi ném lại.
    """
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_section_by_id(db: Session, section_id: int) -> Section | None:
    """Tìm chương học theo mã định danh.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        section_id: Mã chương học cần xử lý.

    Returns:
        Đối tượng Section; None nếu không tìm thấy.
    """
    return db.query(Section).filter(Section.id == section_id).first()


def get_quiz_by_id(db: Session, quiz_id: int) -> Quiz | None:
    """Tìm bài trắc nghiệm theo mã định danh.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        quiz_id: Mã bài trắc nghiệm cần xử lý.

    Returns:
        Đối tượng Quiz; None nếu không tìm thấy.
    """
    return db.query(Quiz).filter(Quiz.id == quiz_id).first()


def lock_quiz_for_submission(db: Session, *, quiz_id: int) -> Quiz | None:
    """Khóa bài trắc nghiệm trong giao dịch nộp bài hiện tại.

    Đây là khóa bi quan: PostgreSQL dùng SELECT FOR UPDATE; SQLite dùng
    UPDATE nguyên tử không đổi giá trị để tuần tự hóa các writer. Khóa được
    lấy trước khi đếm lượt thi để tránh trùng attempt_number khi các bên
    ghi cùng tuân thủ giao thức khóa và mức cô lập phù hợp. Bên gọi phải
    đếm và lưu attempt/answers trong cùng giao dịch. Khóa giải phóng khi
    commit hoặc rollback; hàm không tự commit. PostgreSQL khóa mọi lượt nộp
    cùng quiz; SQLite tuần tự hóa writer của database. Cơ chế này không
    chống tạo hai attempt do gửi trùng.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        quiz_id: Mã bài trắc nghiệm cần xử lý.

    Returns:
        Đối tượng Quiz đã làm mới; None nếu không tìm thấy.

    Raises:
        RuntimeError: Hệ quản trị cơ sở dữ liệu chưa được hỗ trợ.
        SQLAlchemyError: Truy vấn hoặc thao tác lấy khóa thất bại.
    """
    dialect = db.get_bind().dialect.name
    quiz_query = db.query(Quiz).filter(Quiz.id == quiz_id)

    if dialect == "postgresql":
        return quiz_query.with_for_update().populate_existing().first()

    if dialect == "sqlite":
        # SQLite bỏ qua SELECT FOR UPDATE; ghi không đổi giá trị để lấy khóa.
        updated_rows = quiz_query.update(
            {Quiz.id: Quiz.id},
            synchronize_session=False,
        )
        if not updated_rows:
            return None
        db.expire_all()
        return get_quiz_by_id(db, quiz_id)

    raise RuntimeError(
        f"Quiz submission locking is not configured for {dialect}."
    )


def get_quiz_by_section(db: Session, section_id: int) -> Quiz | None:
    """Tìm bài trắc nghiệm đầu tiên thuộc chương học.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        section_id: Mã chương học cần xử lý.

    Returns:
        Đối tượng Quiz; None nếu chương chưa có bài trắc nghiệm.
    """
    return db.query(Quiz).filter(Quiz.section_id == section_id).first()


def get_questions_by_quiz(db: Session, quiz_id: int) -> list[Question]:
    """Lấy các câu hỏi của một bài trắc nghiệm.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        quiz_id: Mã bài trắc nghiệm cần xử lý.

    Returns:
        Danh sách Question sắp theo position tăng dần.
    """
    return (
        db.query(Question)
        .filter(Question.quiz_id == quiz_id)
        .order_by(Question.position.asc())
        .all()
    )


def get_question_by_id(db: Session, question_id: int) -> Question | None:
    """Tìm câu hỏi theo mã định danh.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        question_id: Mã câu hỏi cần tìm.

    Returns:
        Đối tượng Question; None nếu không tìm thấy.
    """
    return db.query(Question).filter(Question.id == question_id).first()


def create_quiz(
    db: Session,
    *,
    section_id: int,
    title: str,
    passing_score: float = MIN_PASSING_SCORE,
    is_approved: bool = False,
) -> Quiz:
    """Tạo và commit một bài trắc nghiệm.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        section_id: Mã chương học cần xử lý.
        title: Tiêu đề bài trắc nghiệm.
        passing_score: Ngưỡng điểm đạt được lưu trong cấu hình bài thi.
        is_approved: Trạng thái phê duyệt bài trắc nghiệm.

    Returns:
        Đối tượng Quiz đã được đọc lại sau commit.

    Raises:
        SQLAlchemyError: Thao tác thêm, commit hoặc đọc lại thất bại.
    """
    quiz = Quiz(
        section_id=section_id,
        title=title,
        passing_score=passing_score,
        is_approved=is_approved,
    )
    try:
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
    except Exception:
        db.rollback()
        raise
    return quiz


def create_question(
    db: Session,
    *,
    quiz_id: int,
    question: str,
    options_json: list[str],
    correct_answer: str,
    explanation: str | None = None,
    position: int = 1,
) -> Question:
    """Tạo và commit một câu hỏi trong bài trắc nghiệm.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        quiz_id: Mã bài trắc nghiệm cần xử lý.
        question: Nội dung câu hỏi.
        options_json: Danh sách lựa chọn được lưu trong cột JSON.
        correct_answer: Nội dung lựa chọn đúng của câu hỏi.
        explanation: Lời giải thích đáp án; có thể là None.
        position: Thứ tự câu hỏi trong bài trắc nghiệm.

    Returns:
        Đối tượng Question đã được đọc lại sau commit.

    Raises:
        SQLAlchemyError: Thao tác thêm, commit hoặc đọc lại thất bại.
    """
    new_question = Question(
        quiz_id=quiz_id,
        question=question,
        options_json=options_json,
        correct_answer=correct_answer,
        explanation=explanation,
        position=position,
    )
    try:
        db.add(new_question)
        db.commit()
        db.refresh(new_question)
    except Exception:
        db.rollback()
        raise
    return new_question


def count_user_attempts(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
) -> int:
    """Đếm lượt thi của học viên trong một bài trắc nghiệm.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        quiz_id: Mã bài trắc nghiệm cần xử lý.

    Returns:
        Tổng số lượt thi đang lưu cho học viên và bài trắc nghiệm.
    """
    return (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.quiz_id == quiz_id,
        )
        .count()
    )


def create_attempt(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
    score: float,
    passed: bool,
    attempt_number: int,
) -> QuizAttempt:
    """Thêm lượt thi vào giao dịch hiện tại và lấy mã định danh.

    Bên gọi chịu trách nhiệm commit cùng với các câu trả lời.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        quiz_id: Mã bài trắc nghiệm cần xử lý.
        score: Điểm của lượt thi theo thang phần trăm.
        passed: Trạng thái đạt đã được tầng Service xác định.
        attempt_number: Số thứ tự lượt thi của học viên trong bài trắc
            nghiệm.

    Returns:
        Đối tượng QuizAttempt đã flush nhưng chưa được commit.

    Raises:
        SQLAlchemyError: Thao tác thêm hoặc flush không thành công.
    """
    attempt = QuizAttempt(
        student_id=student_id,
        quiz_id=quiz_id,
        score=score,
        passed=passed,
        attempt_number=attempt_number,
    )
    db.add(attempt)
    db.flush()
    return attempt


def save_attempt_answers(
    db: Session,
    *,
    attempt_id: int,
    answers_data: list[dict],
) -> None:
    """Thêm chi tiết câu trả lời vào giao dịch của lượt thi.

    Lưu cùng giao dịch với attempt; lỗi flush/commit được bên gọi xử lý.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        attempt_id: Mã lượt thi sở hữu các câu trả lời.
        answers_data: Danh sách mã câu hỏi, lựa chọn và kết quả chấm.

    Returns:
        None; các câu trả lời được thêm vào Session, chưa commit.

    Raises:
        KeyError: Một mục answers_data thiếu trường bắt buộc.
    """
    answers = [
        QuizAnswer(
            attempt_id=attempt_id,
            question_id=answer["question_id"],
            selected_answer=answer["selected_answer"],
            is_correct=answer["is_correct"],
        )
        for answer in answers_data
    ]
    db.add_all(answers)


def has_passed_quiz(
    db: Session,
    *,
    student_id: int,
    quiz_id: int,
) -> bool:
    """Kiểm tra học viên có lượt thi đạt ngưỡng tối thiểu.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        quiz_id: Mã bài trắc nghiệm cần xử lý.

    Returns:
        True nếu có lượt thi passed=True và score lớn hơn hoặc bằng 80.
    """
    return (
        _passed_attempts_query(db, student_id=student_id)
        .filter(QuizAttempt.quiz_id == quiz_id)
        .first()
        is not None
    )


def _passed_attempts_query(
    db: Session, *, student_id: int
) -> Query[QuizAttempt]:
    """Tạo truy vấn các lượt thi đạt của một học viên.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.

    Returns:
        Query chưa thực thi, lọc passed=True và score tối thiểu 80.
    """
    return (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.passed.is_(True),
            QuizAttempt.score >= MIN_PASSING_SCORE,
        )
    )


def list_section_quiz_progress(
    db: Session,
    *,
    student_id: int,
    course_id: int,
) -> list[tuple[int, bool]]:
    """Lấy điều kiện hoàn thành các chương trong một truy vấn.

    Chương không có quiz đáp ứng điều kiện ngay. Nếu có quiz, mỗi quiz phải
    có ít nhất một lượt passed=True và score tối thiểu 80.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        course_id: Mã khóa học chứa các chương cần kiểm tra.

    Returns:
        Các hàng gồm mã chương và cờ đáp ứng điều kiện, theo thứ tự học.
    """
    passed_attempt = (
        _passed_attempts_query(db, student_id=student_id)
        .filter(QuizAttempt.quiz_id == Quiz.id)
        .exists()
    )
    unmet_quiz = (
        db.query(Quiz.id)
        .filter(
            Quiz.section_id == Section.id,
            ~passed_attempt,
        )
        .exists()
    )
    return (
        db.query(Section.id, (~unmet_quiz).label("requirements_met"))
        .filter(Section.course_id == course_id)
        .order_by(Section.position.asc(), Section.id.asc())
        .all()
    )


def list_attempts_by_student(
    db: Session,
    *,
    student_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[QuizAttempt]:
    """Lấy lịch sử lượt thi của học viên có phân trang.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        skip: Số lượt thi bỏ qua khi phân trang.
        limit: Số lượt thi tối đa cần lấy.

    Returns:
        Danh sách QuizAttempt sắp theo thời điểm mới nhất.
    """
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.student_id == student_id)
        .order_by(QuizAttempt.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_attempts_by_student_with_quiz_title(
    db: Session,
    *,
    student_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[tuple[QuizAttempt, str | None]]:
    """Lấy lịch sử lượt thi kèm tiêu đề bằng một truy vấn.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        skip: Số lượt thi bỏ qua khi phân trang.
        limit: Số lượt thi tối đa cần lấy.

    Returns:
        Các hàng gồm QuizAttempt và tiêu đề quiz; tiêu đề có thể là None.
    """
    return (
        db.query(QuizAttempt, Quiz.title)
        .outerjoin(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .filter(QuizAttempt.student_id == student_id)
        .order_by(QuizAttempt.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
