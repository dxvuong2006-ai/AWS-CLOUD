from sqlalchemy.orm import Session

from app.repositories import quizzes_repo


class SectionLockedError(Exception):
    """Báo chương học chưa đáp ứng điều kiện mở khóa.

    Vai trò kiến trúc: Service.
    """

    pass


def is_section_unlocked(
    db: Session,
    *,
    student_id: int,
    course_id: int,
    section_id: int,
) -> bool:
    """Kiểm tra một chương đã đáp ứng thứ tự mở khóa hay chưa.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        course_id: Mã khóa học chứa các chương cần kiểm tra.
        section_id: Mã chương học cần xử lý.

    Returns:
        True nếu chương tồn tại và các chương trước đáp ứng điều kiện.
    """
    return any(
        item["section_id"] == section_id and item["is_unlocked"]
        for item in get_course_unlock_status(
            db,
            student_id=student_id,
            course_id=course_id,
        )
    )


def assert_section_unlocked(
    db: Session,
    *,
    student_id: int,
    course_id: int,
    section_id: int,
) -> None:
    """Chặn truy cập chương chưa đáp ứng điều kiện mở khóa.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        course_id: Mã khóa học chứa các chương cần kiểm tra.
        section_id: Mã chương học cần xử lý.

    Returns:
        None nếu chương đã được mở khóa.

    Raises:
        SectionLockedError: Không có chương hoặc điều kiện tiến độ chưa
            đạt.
    """
    if not is_section_unlocked(
        db,
        student_id=student_id,
        course_id=course_id,
        section_id=section_id,
    ):
        raise SectionLockedError(
            "Previous section requirements must be met to unlock this section."
        )


def get_course_unlock_status(
    db: Session,
    *,
    student_id: int,
    course_id: int,
) -> list[dict]:
    """Tính trạng thái mở khóa tuần tự cho các chương.

    Chương đầu được mở. Một chương chưa đạt làm khóa mọi chương sau. Chương
    không có quiz không chặn tiến độ; chương có quiz cần đạt từng quiz với
    passed=True và score tối thiểu 80.

    Args:
        db: Session SQLAlchemy được bên gọi cung cấp.
        student_id: Mã học viên có tiến độ hoặc lượt thi cần xử lý.
        course_id: Mã khóa học chứa các chương cần kiểm tra.

    Returns:
        Danh sách section_id/is_unlocked theo thứ tự chương học.
    """
    progress = quizzes_repo.list_section_quiz_progress(
        db,
        student_id=student_id,
        course_id=course_id,
    )
    status = []
    is_unlocked = True
    for section_id, requirements_met in progress:
        status.append(
            {
                "section_id": section_id,
                "is_unlocked": is_unlocked,
            }
        )
        is_unlocked = is_unlocked and requirements_met
    return status
