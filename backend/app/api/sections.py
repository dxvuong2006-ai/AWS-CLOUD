from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_instructor
from app.models.user import User
from app.schemas.section import SectionCreateRequest, SectionResponse
from app.services import section_service

router = APIRouter(tags=["Sections"])

# api: POST /courses/{course_id}/sections
@router.post(
    "/courses/{course_id}/sections",
    response_model=SectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_section(
    course_id: int,
    payload: SectionCreateRequest,
    db: Session = Depends(get_db),
    instructor: User = Depends(require_instructor),
):
    try:
        return section_service.create_section(
            db=db,
            course_id=course_id,
            instructor_id=instructor.id,
            title=payload.title,
            position=payload.position,
        )
    except section_service.CourseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except section_service.CourseOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A section with this position already exists in the course.",
        )

# api: GET /courses/{course_id}/sections
@router.get("/courses/{course_id}/sections", response_model=list[SectionResponse])
def list_course_sections(
    course_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return section_service.list_sections_for_course(
            db, course_id=course_id, user_id=user.id, user_role=str(user.role),
        )
    except section_service.CourseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except section_service.CourseAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc