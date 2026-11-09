#Router kiểm duyệt học liệu AI
"""Cung cấp API bản nháp và phê duyệt dành cho giảng viên."""

from fastapi import APIRouter, Depends, HTTPException
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.adapters.ai.bedrock_ai import BedrockAIAdapter
from app.dependencies import get_db, require_instructor
from app.models.user import User
from app.schemas.review import (
    DraftApproval, DraftGeneration, DraftUpdate, ReviewResponse,
)
from app.services import review_service
from app.models.course import Course
from app.models.section import Section
from app.models.lesson import Lesson

router = APIRouter(tags=["Instructor review"])


@router.get("/instructor/review-queue")
def list_review_queue(
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    lessons = db.scalars(
        select(Lesson)
        .join(Section, Section.id == Lesson.section_id)
        .join(Course, Course.id == Section.course_id)
        .where(
            Course.instructor_id == instructor.id,
            Lesson.status.in_(["REVIEW_REQUIRED", "PUBLISHED"]),
        )
        .order_by(Lesson.updated_at.desc(), Lesson.id.desc())
    ).all()
    rows = []
    for lesson in lessons:
        section = db.get(Section, lesson.section_id)
        course = db.get(Course, section.course_id) if section else None
        rows.append({
            "id": lesson.id,
            "title": lesson.title,
            "course_id": course.id if course else None,
            "course_title": course.title if course else "",
            "processing_status": "READY" if lesson.status == "REVIEW_REQUIRED" else "PUBLISHED",
            "status": lesson.status,
        })
    return rows


def _call(operation, **kwargs) -> ReviewResponse:
    """Chuyển lỗi nghiệp vụ thành phản hồi HTTP phù hợp.

    Args:
        operation: Hàm nghiệp vụ được thực thi.
        **kwargs: Tham số đã được FastAPI kiểm tra.

    Returns:
        DTO bản nháp, không trả lỗi giả dưới mã 200.
    """
    try:
        return operation(**kwargs)
    except review_service.ReviewError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, "Invalid draft or AI response.") from exc
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, "AI service is unavailable.") from exc
    except IntegrityError as exc:
        raise HTTPException(409, "Concurrent draft change; retry.") from exc


@router.post(
    "/lessons/{lesson_id}/review-drafts",
    response_model=ReviewResponse, status_code=201,
)
def generate_draft(
    lesson_id: int, payload: DraftGeneration,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
) -> ReviewResponse:
    """Sinh nội dung mới và lưu trạng thái chờ duyệt.

    Args:
        lesson_id: Mã bài học thuộc khóa học của giảng viên.
        payload: Transcript và cấu hình dự phòng tường minh.
        db: Session hiện tại.
        instructor: Giảng viên từ dependency xác thực.

    Returns:
        Bản nháp REVIEW_REQUIRED đã lưu nguyên tử.
    """
    return _call(
        review_service.generate_draft, db=db, lesson_id=lesson_id,
        instructor_id=instructor.id, payload=payload,
        ai=BedrockAIAdapter(allow_fallback=payload.allow_fallback),
    )


@router.get(
    "/lessons/{lesson_id}/review-draft", response_model=ReviewResponse,
)
def get_draft(
    lesson_id: int, db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
) -> ReviewResponse:
    """Lấy bản nháp gồm đáp án dành riêng cho giảng viên.

    Args:
        lesson_id: Mã bài học.
        db: Session hiện tại.
        instructor: Giảng viên đã xác thực.

    Returns:
        Nội dung và dấu phiên bản hiện tại.
    """
    return _call(
        review_service.get_draft, db=db, lesson_id=lesson_id,
        instructor_id=instructor.id,
    )


@router.put(
    "/lessons/{lesson_id}/review-draft", response_model=ReviewResponse,
)
def update_draft(
    lesson_id: int, payload: DraftUpdate,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
) -> ReviewResponse:
    """Lưu chỉnh sửa bản nháp sau khi kiểm tra schema.

    Args:
        lesson_id: Mã bài học.
        payload: Toàn bộ nội dung mới và dấu phiên bản đã xem.
        db: Session hiện tại.
        instructor: Giảng viên đã xác thực.

    Returns:
        Nội dung vẫn ở trạng thái REVIEW_REQUIRED.
    """
    return _call(
        review_service.update_draft, db=db, lesson_id=lesson_id,
        instructor_id=instructor.id, payload=payload,
    )


@router.post(
    "/lessons/{lesson_id}/review-draft/approvals",
    response_model=ReviewResponse,
)
def approve_draft(
    lesson_id: int, payload: DraftApproval,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
) -> ReviewResponse:
    """Phê duyệt phiên bản được giảng viên xác nhận tường minh.

    Args:
        lesson_id: Mã bài học.
        payload: Dấu phiên bản cần duyệt.
        db: Session hiện tại.
        instructor: Giảng viên đã xác thực.

    Returns:
        Bản nháp đã chuyển PUBLISHED.
    """
    return _call(
        review_service.approve_draft, db=db, lesson_id=lesson_id,
        instructor_id=instructor.id, payload=payload,
    )


@router.get("/lessons/{lesson_id}/ai-content")
def get_ai_content(
    lesson_id: int, db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
) -> dict:
    """Lấy nội dung AI và transcript của bài học thuộc giảng viên.

    Args:
        lesson_id: Mã bài học.
        db: Session hiện tại.
        instructor: Giảng viên đã xác thực.

    Returns:
        Bản nháp cùng transcript đã lưu.
    """
    draft = _call(
        review_service.get_draft, db=db, lesson_id=lesson_id,
        instructor_id=instructor.id,
    )
    from app.repositories import review_repo

    lesson, _ = review_repo.get_context(db, lesson_id)
    return {**draft.model_dump(), "transcript": lesson.transcript_json}


@router.patch("/lessons/{lesson_id}/ai-content", response_model=ReviewResponse)
def patch_ai_content(
    lesson_id: int, payload: dict,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
) -> ReviewResponse:
    """Cập nhật một phần bản nháp có kiểm tra phiên bản.

    Args:
        lesson_id: Mã bài học.
        payload: Trường cần sửa và expected_revision đã xem.
        db: Session hiện tại.
        instructor: Giảng viên đã xác thực.

    Returns:
        Nội dung nháp sau khi cập nhật.
    """
    from pydantic import ValidationError

    current = _call(
        review_service.get_draft, db=db, lesson_id=lesson_id,
        instructor_id=instructor.id,
    )
    allowed = {"title", "summary", "key_concepts", "quiz_title", "questions"}
    if set(payload) - (allowed | {"expected_revision"}):
        raise HTTPException(422, "Unsupported draft field.")
    values = current.model_dump(include=allowed)
    values.update(payload)
    try:
        update = DraftUpdate.model_validate(values)
    except ValidationError as exc:
        raise HTTPException(422, "Invalid draft update.") from exc
    return _call(
        review_service.update_draft, db=db, lesson_id=lesson_id,
        instructor_id=instructor.id, payload=update,
    )


@router.post("/lessons/{lesson_id}/approve", response_model=ReviewResponse)
def approve_ai_content(
    lesson_id: int, payload: DraftApproval,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
) -> ReviewResponse:
    """Phê duyệt phiên bản nháp được xác nhận bởi giảng viên.

    Args:
        lesson_id: Mã bài học.
        payload: Phiên bản cần duyệt.
        db: Session hiện tại.
        instructor: Giảng viên đã xác thực.

    Returns:
        Nội dung sau khi phê duyệt.
    """
    return _call(
        review_service.approve_draft, db=db, lesson_id=lesson_id,
        instructor_id=instructor.id, payload=payload,
    )
