#Quản lý luồng kiểm duyệt học liệu của giảng viên (Human-in-the-loop)
"""Điều phối sinh bản nháp và phê duyệt bởi giảng viên sở hữu khóa học."""

import hashlib
import json

from sqlalchemy.orm import Session

from app.adapters.ai.base import BaseAIAdapter
from app.adapters.storage.s3_storage import S3StorageAdapter
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
        flashcards=[
            dict(front=item.front, back=item.back, position=item.position)
            for item in review_repo.get_flashcards(db, lesson.id)
        ],
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
        flashcards=[
            dict(
                front=item.term if hasattr(item, "term") else item["term"],
                back=item.definition if hasattr(item, "definition") else item["definition"],
                position=index,
            )
            for index, item in enumerate(concepts, 1)
        ],
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


def approve_lesson(db: Session, lesson_id: int, instructor_id: int,
                   expected_revision=None, storage_adapter=None):
    """Duyệt bài sau khi kiểm tra quyền, nội dung và video đã xử lý."""
    from botocore.exceptions import BotoCoreError, ClientError
    from sqlalchemy.exc import OperationalError
    from app.repositories import lessons_repo, courses_repo
    from app.utils.errors import NotFoundError, ForbiddenError, ExternalServiceError

    try:
        lesson = lessons_repo.get_by_id(db, lesson_id)
        if lesson is None:
            raise NotFoundError("Lesson not found.")
        section = lessons_repo.get_section(db, lesson.section_id)
        if section is None:
            raise NotFoundError("Section not found.")
        course = lessons_repo.get_course(db, section.course_id)
        if course is None:
            raise NotFoundError("Course not found.")
        if course.instructor_id != instructor_id:
            raise ForbiddenError("You do not own this course.")
        course = courses_repo.lock_by_id(db, course.id)
        if course is None:
            raise NotFoundError("Course not found.")
        if course.instructor_id != instructor_id:
            raise ForbiddenError("You do not own this course.")
        lesson = lessons_repo.lock_by_id(db, lesson_id)
        if lesson is None or lesson.section_id != section.id:
            raise NotFoundError("Lesson not found.")
        def response():
            """Tạo dấu phiên bản ổn định từ nội dung bài đã duyệt."""
            revision = hashlib.sha256(json.dumps(
                {"lesson_id": lesson.id, "transcript": lesson.transcript_json,
                 "summary": lesson.summary, "key_concepts": lesson.key_concepts_json},
                sort_keys=True, ensure_ascii=False, default=str,
            ).encode("utf-8")).hexdigest()
            return {"lesson_id": lesson.id, "status": lesson.status,
                    "revision": revision}

        if lesson.status == "PUBLISHED":
            if expected_revision is not None and expected_revision != response()["revision"]:
                quiz = review_repo.get_quiz(db, lesson.section_id, lock=True)
                if quiz is None or _response(db, lesson, quiz).revision != expected_revision:
                    raise ConflictError("Draft changed.", code="REVIEW_CHANGED")
            result = response()
            db.commit()
            return result
        if course.status != "DRAFT":
            raise ConflictError("Course is not a draft.", code="COURSE_NOT_DRAFT")
        if lesson.status != "REVIEW_REQUIRED":
            raise ConflictError("Lesson is not reviewable.", code="LESSON_NOT_REVIEWABLE")
        if not lesson.processed_video_key:
            raise ConflictError("Processed video is required.", code="PROCESSED_VIDEO_REQUIRED")
        validate_review_content(lesson)
        if expected_revision is not None:
            quiz = review_repo.get_quiz(db, lesson.section_id, lock=True)
            current = _response(db, lesson, quiz)
            if current.revision != expected_revision:
                raise ConflictError("Draft changed.", code="REVIEW_CHANGED")
        try:
            storage = storage_adapter or S3StorageAdapter()
            metadata = storage.head_video(lesson.processed_video_key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NotFound", "404"}:
                raise ConflictError("Processed video is missing.", code="PROCESSED_VIDEO_REQUIRED") from None
            raise ExternalServiceError("Storage unavailable.", code="APPROVAL_STORAGE_UNAVAILABLE") from None
        except BotoCoreError:
            raise ExternalServiceError("Storage unavailable.", code="APPROVAL_STORAGE_UNAVAILABLE") from None
        if metadata.get("ContentLength", 0) <= 0:
            raise ConflictError("Processed video is empty.", code="INVALID_PROCESSED_VIDEO")
        quiz = review_repo.get_quiz(db, lesson.section_id, lock=True)
        if quiz is not None:
            review_repo.approve(db, lesson, quiz)
        else:
            lesson.status = "PUBLISHED"
            db.flush()
        db.commit()
        return response()
    except OperationalError as exc:
        db.rollback()
        if getattr(exc.orig, "pgcode", None) == "55P03":
            raise ConflictError("Review is busy.", code="REVIEW_BUSY") from None
        raise
    except Exception:
        db.rollback()
        raise
