
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.enrollment import EnrollmentResponse, MyCourseEnrollmentResponse
from app.services import enrollment_service

router = APIRouter(tags=["Enrollments"])


@router.get(
    "/students/me/courses",
    response_model=list[MyCourseEnrollmentResponse],
)
def list_my_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = getattr(current_user.role, "value", current_user.role)
    if str(role).upper() != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can list enrolled courses.",
        )

    return enrollment_service.list_student_courses(db, current_user.id)

# api: POST /courses/{course_id}/enroll
@router.post(
    "/courses/{course_id}/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def enroll_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Chỉ sinh viên mới được đăng ký khóa học.
    role = getattr(current_user.role, "value", current_user.role)

    if str(role).upper() != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can enroll in courses.",
        )

    try:
        return enrollment_service.enroll_course(
            db=db,
            student_id=current_user.id,
            course_id=course_id,
        )

    except enrollment_service.CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    except enrollment_service.CourseNotPublishedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course is not published.",
        )

    except enrollment_service.AlreadyEnrolledError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already enrolled in this course.",
        )
