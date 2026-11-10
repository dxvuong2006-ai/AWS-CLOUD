from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_instructor
from app.schemas.course import CourseCreateRequest, CourseResponse, CourseUpdateRequest
from app.services import course_service
from app.repositories import courses_repo, sections_repo
from sqlalchemy import func, select
from app.models.course import Course
from app.models.section import Section
from app.models.lesson import Lesson
from app.models.enrollment import Enrollment

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post(
    "/{course_id}/publish", response_model=CourseResponse,
    responses={
        401: {"description": "Invalid user identity."}, 403: {"description": "Owning instructor required."},
        404: {"description": "Course not found."}, 409: {"description": "Content not approved or concurrent operation."},
    },
)
def publish_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_instructor),
):
    return course_service.publish_course(db, course_id, instructor_id=current_user.id)

# POST /courses: Giảng viên tạo khóa học
@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course(
    request: CourseCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_instructor),
):
    return course_service.create_course(
        db=db,
        instructor_id=current_user.id,
        data=request,
    )

# GET /courses: lấy danh sách courses đã publish
@router.get("", response_model=list[CourseResponse])
def list_courses(db: Session = Depends(get_db)):
    return course_service.get_courses(db)


@router.get("/instructor/me", response_model=list[CourseResponse])
def list_instructor_courses(
    db: Session = Depends(get_db),
    current_user=Depends(require_instructor),
):
    courses = courses_repo.get_courses_by_instructor(db, current_user.id)
    return [
        {
            **{column.name: getattr(course, column.name) for column in course.__table__.columns},
            "sections": [
                {
                    "id": section.id,
                    "course_id": section.course_id,
                    "title": section.title,
                    "position": section.position,
                    "lessons": list(db.scalars(
                        select(Lesson).where(Lesson.section_id == section.id)
                        .order_by(Lesson.position.asc(), Lesson.id.asc())
                    ).all()),
                }
                for section in db.scalars(
                    select(Section).where(Section.course_id == course.id)
                    .order_by(Section.position.asc(), Section.id.asc())
                ).all()
            ],
        }
        for course in courses
    ]

# GET /courses/{id}: Chi tiết/outline course.
@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: int, db: Session = Depends(get_db)):
    course = course_service.get_course_detail(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found",
        )

    return course

# PATCH /courses/{course_id}: Giảng viên cập nhật khóa học
@router.patch(
    "/{course_id}",
    response_model=CourseResponse,
)
def update_course(
    course_id: int,
    request: CourseUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_instructor),
):
    course = course_service.update_course(
        db=db,
        course_id=course_id,
        instructor_id=current_user.id,
        data=request,
    )

    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found or access denied",
        )

    return course
