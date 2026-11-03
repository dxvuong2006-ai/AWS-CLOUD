from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user, require_instructor
from app.models.user import User
from app.schemas.lesson import (
    LessonCreateRequest,
    LessonResponse,
    LessonUpdateRequest,
    LessonVideoUrlResponse,
)
from app.services import lesson_service

router = APIRouter(tags=["Lessons"])


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, lesson_service.SectionNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, lesson_service.CourseNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, lesson_service.LessonNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, lesson_service.CourseOwnershipError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, lesson_service.PublishedCourseRequiredError):
        raise HTTPException(status_code=403, detail="Lesson is not available.")
    if isinstance(exc, lesson_service.LessonAccessDeniedError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc))
    raise exc

# api: POST /sections/{section_id}/lessons
@router.post(
    "/sections/{section_id}/lessons",
    response_model=LessonResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lesson(
    section_id: int,
    payload: LessonCreateRequest,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    try:
        return lesson_service.create_lesson(
            db=db,
            section_id=section_id,
            instructor_id=instructor.id,
            title=payload.title,
            position=payload.position,
        )
    except (
        lesson_service.SectionNotFoundError,
        lesson_service.CourseNotFoundError,
        lesson_service.CourseOwnershipError,
        ValueError,
    ) as exc:
        _raise_service_error(exc)

# api: GET /lessons/{lesson_id}
@router.get("/lessons/{lesson_id}", response_model=LessonResponse)
def get_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return lesson_service.get_lesson_for_user(
            db,
            lesson_id,
            user_id=user.id,
            user_role=user.role,
        )
    except (
        lesson_service.LessonNotFoundError,
        lesson_service.SectionNotFoundError,
        lesson_service.CourseNotFoundError,
        lesson_service.CourseOwnershipError,
        lesson_service.PublishedCourseRequiredError,
        lesson_service.LessonAccessDeniedError,
    ) as exc:
        _raise_service_error(exc)

# API: GET /lessons/{lesson_id}/video-url
@router.get(
    "/lessons/{lesson_id}/video-url",
    response_model=LessonVideoUrlResponse,
    responses={
        401: {"description": "User identity could not be resolved."},
        403: {"description": "The current user cannot access this lesson."},
        404: {"description": "Lesson, attached video, or S3 object not found."},
        409: {"description": "The selected video is not an MP4 file."},
        502: {"description": "S3 denied access or video storage is unavailable."},
    },
)
def get_lesson_video_url(
    lesson_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return lesson_service.get_video_url_for_user(
            db, lesson_id, user_id=user.id, user_role=user.role
        )
    except (
        lesson_service.LessonNotFoundError,
        lesson_service.SectionNotFoundError,
        lesson_service.CourseNotFoundError,
        lesson_service.CourseOwnershipError,
        lesson_service.PublishedCourseRequiredError,
        lesson_service.LessonAccessDeniedError,
    ) as exc:
        _raise_service_error(exc)


# API: GET /sections/{section_id}/lessons
@router.get(
    "/sections/{section_id}/lessons",
    response_model=list[LessonResponse],
)
def list_lessons(
    section_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return lesson_service.list_lessons_for_section(
            db,
            section_id,
            user_id=user.id,
            user_role=user.role,
            skip=skip,
            limit=limit,
        )
    except (
        lesson_service.SectionNotFoundError,
        lesson_service.CourseNotFoundError,
        lesson_service.CourseOwnershipError,
        lesson_service.PublishedCourseRequiredError,
        lesson_service.LessonAccessDeniedError,
    ) as exc:
        _raise_service_error(exc)

# api: PATCH /lessons/{lesson_id}
@router.patch("/lessons/{lesson_id}", response_model=LessonResponse)
def update_lesson(
    lesson_id: int,
    payload: LessonUpdateRequest,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    try:
        return lesson_service.update_lesson(
            db=db,
            lesson_id=lesson_id,
            instructor_id=instructor.id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except (
        lesson_service.LessonNotFoundError,
        lesson_service.SectionNotFoundError,
        lesson_service.CourseNotFoundError,
        lesson_service.CourseOwnershipError,
        ValueError,
    ) as exc:
        _raise_service_error(exc)
