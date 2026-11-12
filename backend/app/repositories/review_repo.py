#Là tầng truy vấn dữ liệu phục vụ quy trình kiểm duyệt học liệu do AI sinh ra.
"""Đọc và ghi bản nháp bằng giao dịch dùng chung cho bài học và quiz."""

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz, QuizAttempt
from app.models.section import Section
from app.models.user import User
from app.schemas.review import DraftContent


@contextmanager
def transaction(db: Session) -> Iterator[None]:
    """Commit một lần và rollback toàn bộ khi ghi bản nháp thất bại.

    Args:
        db: Session do dependency quản lý.

    Yields:
        Phạm vi giao dịch; không tự đóng Session của bên gọi.
    """
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_context(db: Session, lesson_id: int) -> tuple[Lesson, Course] | None:
    """Lấy bài học cùng khóa học để xác minh quyền sở hữu.

    Args:
        db: Session hiện tại.
        lesson_id: Mã bài học.

    Returns:
        Cặp Lesson, Course hoặc None nếu không tồn tại.
    """
    return (
        db.query(Lesson, Course)
        .join(Section, Lesson.section_id == Section.id)
        .join(Course, Section.course_id == Course.id)
        .filter(Lesson.id == lesson_id).first()
    )


def is_instructor(db: Session, user_id: int) -> bool:
    """Kiểm tra vai trò từ dữ liệu máy chủ.

    Args:
        db: Session hiện tại.
        user_id: Mã người dùng.

    Returns:
        True nếu tài khoản là giảng viên.
    """
    return db.query(User.id).filter(
        User.id == user_id, User.role == "INSTRUCTOR",
    ).first() is not None


def lock_section(db: Session, lesson_id: int) -> None:
    """Tuần tự hóa việc tạo, sửa và duyệt nội dung cùng section.

    Args:
        db: Session trong giao dịch ghi.
        lesson_id: Bài học xác định section cần khóa.

    Returns:
        None; khóa được giữ đến commit hoặc rollback.
    """
    section_id = select(Lesson.section_id).where(
        Lesson.id == lesson_id,
    ).scalar_subquery()
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        db.execute(
            update(Section).where(Section.id == section_id)
            .values(title=Section.title),
            execution_options={"synchronize_session": False},
        )
    elif dialect == "postgresql":
        db.query(Section).filter(
            Section.id == section_id,
        ).with_for_update().first()
    else:
        raise RuntimeError("Review supports SQLite and PostgreSQL only.")
    db.expire_all()


def get_quiz(
    db: Session, section_id: int, *, lock: bool = False,
) -> Quiz | None:
    """Lấy quiz và khóa đồng bộ với luồng nộp bài khi ghi.

    Args:
        db: Session hiện tại.
        section_id: Mã section.
        lock: Khóa quiz trên PostgreSQL; SQLite đã khóa writer.

    Returns:
        Quiz hoặc None.
    """
    query = db.query(Quiz).filter(Quiz.section_id == section_id)
    if lock:
        query = query.populate_existing().with_for_update()
    return query.first()


def get_questions(db: Session, quiz_id: int) -> list[Question]:
    """Đọc toàn bộ câu hỏi trong một truy vấn.

    Args:
        db: Session hiện tại.
        quiz_id: Mã quiz.

    Returns:
        Các câu hỏi theo vị trí.
    """
    return db.query(Question).filter(
        Question.quiz_id == quiz_id,
    ).order_by(Question.position).all()


def get_flashcards(db: Session, lesson_id: int) -> list[Flashcard]:
    """Trả thẻ của lesson theo thứ tự phục vụ bản nháp và revision."""
    return db.query(Flashcard).filter(
        Flashcard.lesson_id == lesson_id,
    ).order_by(Flashcard.position, Flashcard.id).all()


def has_attempts(db: Session, quiz_id: int) -> bool:
    """Kiểm tra đề đã được học viên sử dụng.

    Args:
        db: Session hiện tại.
        quiz_id: Mã quiz.

    Returns:
        True khi có ít nhất một lượt nộp bài.
    """
    return db.query(QuizAttempt.id).filter(
        QuizAttempt.quiz_id == quiz_id,
    ).first() is not None


def replace_content(
    db: Session, lesson: Lesson, quiz: Quiz | None, content: DraftContent,
    *, set_review_status: bool = True,
) -> Quiz:
    """Lưu nội dung hợp lệ và đưa cả bài học, quiz về chờ duyệt.

    Args:
        db: Session đã khóa section và quiz.
        lesson: Bài học đích.
        quiz: Quiz hiện tại hoặc None.
        content: DraftContent đã kiểm tra.
        set_review_status: False cho K5 worker; pipeline finalize mới được chốt
            REVIEW_REQUIRED. Các luồng review thủ công giữ mặc định True.

    Returns:
        Quiz đã flush, chưa commit.
    """
    if quiz is None:
        quiz = Quiz(section_id=lesson.section_id, title=content.quiz_title)
        db.add(quiz)
        db.flush()
    else:
        db.query(Question).filter(
            Question.quiz_id == quiz.id,
        ).delete(synchronize_session=False)
    lesson.title = content.title
    lesson.summary = content.summary
    lesson.key_concepts_json = [
        item.model_dump() for item in content.key_concepts
    ]
    if set_review_status:
        lesson.status = "REVIEW_REQUIRED"
    db.query(Flashcard).filter(
        Flashcard.lesson_id == lesson.id,
    ).delete(synchronize_session=False)
    db.add_all([
        Flashcard(
            lesson_id=lesson.id,
            front=item.front,
            back=item.back,
            position=item.position,
            is_approved=False,
        )
        for item in content.flashcards
    ])
    quiz.title = content.quiz_title
    quiz.is_approved = False
    db.add_all([
        Question(
            quiz_id=quiz.id, position=position,
            question=item.question, options_json=item.options,
            correct_answer=item.correct_answer,
            explanation=item.explanation,
        )
        for position, item in enumerate(content.questions, 1)
    ])
    db.flush()
    return quiz


def approve(db: Session, lesson: Lesson, quiz: Quiz) -> None:
    """Duyệt bài học; quiz chỉ công khai khi không còn bài chờ duyệt.

    Args:
        db: Session đã khóa.
        lesson: Bài học được duyệt tường minh.
        quiz: Quiz dùng chung ở cấp section.

    Returns:
        None; thay đổi vẫn thuộc giao dịch của bên gọi.
    """
    lesson.status = "PUBLISHED"
    db.query(Flashcard).filter(
        Flashcard.lesson_id == lesson.id,
    ).update({"is_approved": True}, synchronize_session=False)
    db.flush()
    pending = db.query(Lesson.id).filter(
        Lesson.section_id == lesson.section_id,
        Lesson.status == "REVIEW_REQUIRED",
    ).first()
    quiz.is_approved = pending is None
    db.flush()


def list_visible_lessons(
    db: Session, section_id: int, *, skip: int, limit: int,
) -> list[Lesson]:
    """Lọc bài đã duyệt trước khi phân trang cho học viên.

    Args:
        db: Session hiện tại.
        section_id: Mã section.
        skip: Số phần tử bỏ qua.
        limit: Số phần tử tối đa.

    Returns:
        Bài đã được publish sau review.
    """
    return db.query(Lesson).filter(
        Lesson.section_id == section_id,
        Lesson.status == "PUBLISHED",
    ).order_by(Lesson.position, Lesson.id).offset(skip).limit(limit).all()
