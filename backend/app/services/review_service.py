#Quản lý luồng kiểm duyệt học liệu của giảng viên (Human-in-the-loop)
"""Điều phối sinh bản nháp và phê duyệt bởi giảng viên sở hữu khóa học."""

import hashlib
import json

from sqlalchemy.orm import Session

from app.adapters.ai.base import BaseAIAdapter
from app.models.lesson import Lesson
from app.models.quiz import Quiz
from app.repositories import review_repo
from app.schemas.review import (
    DraftApproval, DraftContent, DraftGeneration, DraftUpdate, ReviewResponse,
)
from app.utils.errors import ConflictError


class ReviewError(Exception):
    """Biểu diễn lỗi nghiệp vụ duyệt bài với mã HTTP ổn định.

    Vai trò kiến trúc: Service.
    """

    def __init__(self, status_code: int, message: str) -> None:
        """Ghi mã lỗi và thông báo không chứa dữ liệu nội bộ.

        Args:
            status_code: Mã HTTP tương ứng.
            message: Thông báo dành cho giảng viên.
        """
        super().__init__(message)
        self.status_code = status_code


def validate_review_content(lesson: Lesson) -> None:
    """Reject review finalization when generated lesson content is incomplete."""
    transcript = lesson.transcript_json
    summary = lesson.summary
    key_concepts = lesson.key_concepts_json

    if (
        not isinstance(transcript, dict)
        or not transcript
        or not isinstance(summary, str)
        or not summary.strip()
        or not isinstance(key_concepts, list)
        or not key_concepts
    ):
        raise ConflictError(
            "Review content is incomplete.",
            code="REVIEW_CONTENT_INCOMPLETE",
        )


def _owned_lesson(
    db: Session, lesson_id: int, instructor_id: int,
) -> Lesson:
    """Xác minh giảng viên và quyền sở hữu bài học.

    Args:
        db: Session hiện tại.
        lesson_id: Bài học cần duyệt.
        instructor_id: Tài khoản thực hiện.

    Returns:
        Bài học đã được kiểm tra quyền.
    """
    if not review_repo.is_instructor(db, instructor_id):
        raise ReviewError(403, "Instructor role required.")
    context = review_repo.get_context(db, lesson_id)
    if context is None:
        raise ReviewError(404, "Lesson not found.")
    lesson, course = context
    if course.instructor_id != instructor_id:
        raise ReviewError(403, "You do not own this course.")
    return lesson


def _response(
    db: Session, lesson: Lesson, quiz: Quiz | None,
) -> ReviewResponse:
    """Tạo DTO và dấu phiên bản từ nội dung hiện tại.

    Args:
        db: Session hiện tại.
        lesson: Bài học cần biểu diễn.
        quiz: Quiz cấp section.

    Returns:
        Bản nháp gồm đáp án; chỉ dùng trong API giảng viên.
    """
    if quiz is None or lesson.status not in (
        "REVIEW_REQUIRED", "PUBLISHED",
    ):
        raise ReviewError(409, "No reviewable draft exists.")
    values = dict(
        lesson_id=lesson.id, section_id=lesson.section_id, quiz_id=quiz.id,
        title=lesson.title, summary=lesson.summary,
        key_concepts=lesson.key_concepts_json, quiz_title=quiz.title,
        questions=[
            dict(
                question=item.question, options=item.options_json,
                correct_answer=item.correct_answer,
                explanation=item.explanation,
            )
            for item in review_repo.get_questions(db, quiz.id)
        ],
        status=lesson.status, quiz_approved=quiz.is_approved,
    )
    revision = hashlib.sha256(
        json.dumps(values, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    ).hexdigest()
    return ReviewResponse(**values, revision=revision)


def get_draft(
    db: Session, *, lesson_id: int, instructor_id: int,
) -> ReviewResponse:
    """Lấy nội dung chờ duyệt của giảng viên sở hữu.

    Args:
        db: Session hiện tại.
        lesson_id: Mã bài học.
        instructor_id: Mã giảng viên.

    Returns:
        DTO bản nháp và phiên bản hiện tại.
    """
    lesson = _owned_lesson(db, lesson_id, instructor_id)
    return _response(db, lesson, review_repo.get_quiz(db, lesson.section_id))


def _editable(db: Session, quiz: Quiz | None) -> None:
    """Ngăn sửa đề đã có lượt làm bài.

    Args:
        db: Session đã khóa.
        quiz: Quiz hiện có hoặc None.

    Returns:
        None nếu có thể lưu mà không phá lịch sử.
    """
    if quiz is not None and review_repo.has_attempts(db, quiz.id):
        raise ReviewError(409, "Quiz has attempts; a new version is required.")


def generate_draft(
    db: Session, *, lesson_id: int, instructor_id: int,
    payload: DraftGeneration, ai: BaseAIAdapter, transcript_data=None,
) -> ReviewResponse:
    """Sinh nội dung ngoài khóa DB rồi lưu nguyên tử ở trạng thái chờ.

    Args:
        db: Session hiện tại.
        lesson_id: Mã bài học.
        instructor_id: Mã giảng viên.
        payload: Transcript và cấu hình sinh.
        ai: Adapter được tiêm để tránh gọi AWS thật khi kiểm thử.

    Returns:
        Nội dung REVIEW_REQUIRED, kể cả khi dùng Mock.
    """
    _owned_lesson(db, lesson_id, instructor_id)
    summary = ai.generate_summary(payload.transcript)
    concepts = ai.extract_key_concepts(payload.transcript)
    quiz_data = ai.generate_quiz(
        payload.transcript, num_questions=payload.num_questions,
    )
    content = DraftContent(
        title=summary["title"], summary=summary["summary"],
        key_concepts=concepts, quiz_title=summary["title"],
        questions=quiz_data["questions"],
    )
    with review_repo.transaction(db):
        review_repo.lock_section(db, lesson_id)
        lesson = _owned_lesson(db, lesson_id, instructor_id)
        quiz = review_repo.get_quiz(db, lesson.section_id, lock=True)
        _editable(db, quiz)
        quiz = review_repo.replace_content(db, lesson, quiz, content)
        from ai_pipeline.processors.normalize_transcript import normalize_transcript

        previous = transcript_data if transcript_data is not None else lesson.transcript_json
        normalized = normalize_transcript(payload.transcript)
        if isinstance(previous, dict):
            old = normalize_transcript(previous)
            if old["full_text"].strip() == normalized["full_text"].strip():
                normalized["segments"] = old["segments"]
                normalized["language"] = old["language"]
        normalized["text"] = normalized["full_text"]
        lesson.transcript_json = normalized
        result = _response(db, lesson, quiz)
    return result


def update_draft(
    db: Session, *, lesson_id: int, instructor_id: int,
    payload: DraftUpdate,
) -> ReviewResponse:
    """Thay nội dung nháp sau khi kiểm tra phiên bản và quyền.

    Args:
        db: Session hiện tại.
        lesson_id: Mã bài học.
        instructor_id: Mã giảng viên.
        payload: Nội dung đã kiểm tra và dấu phiên bản đã xem.

    Returns:
        Bản nháp mới; không tự phê duyệt.
    """
    with review_repo.transaction(db):
        review_repo.lock_section(db, lesson_id)
        lesson = _owned_lesson(db, lesson_id, instructor_id)
        quiz = review_repo.get_quiz(db, lesson.section_id, lock=True)
        current = _response(db, lesson, quiz)
        if current.revision != payload.expected_revision:
            raise ReviewError(409, "Draft changed; reload before editing.")
        if lesson.status != "REVIEW_REQUIRED":
            raise ReviewError(409, "Only pending drafts can be edited.")
        _editable(db, quiz)
        review_repo.replace_content(db, lesson, quiz, payload)
        result = _response(db, lesson, quiz)
    return result


def approve_draft(
    db: Session, *, lesson_id: int, instructor_id: int,
    payload: DraftApproval,
) -> ReviewResponse:
    """Duyệt đúng phiên bản được giảng viên xác nhận.

    Args:
        db: Session hiện tại.
        lesson_id: Mã bài học.
        instructor_id: Mã giảng viên.
        payload: Dấu phiên bản được duyệt tường minh.

    Returns:
        Nội dung PUBLISHED; quiz chờ các bài nháp khác cùng section.
    """
    with review_repo.transaction(db):
        review_repo.lock_section(db, lesson_id)
        lesson = _owned_lesson(db, lesson_id, instructor_id)
        quiz = review_repo.get_quiz(db, lesson.section_id, lock=True)
        current = _response(db, lesson, quiz)
        if current.revision != payload.expected_revision:
            raise ReviewError(409, "Draft changed; reload before approving.")
        review_repo.approve(db, lesson, quiz)
        result = _response(db, lesson, quiz)
    return result
