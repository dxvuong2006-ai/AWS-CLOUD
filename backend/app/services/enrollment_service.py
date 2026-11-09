
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.enrollment import Enrollment
from app.models.course import Course
from app.models.section import Section
from app.models.lesson import Lesson
from app.models.progress import LessonProgress
from app.models.quiz import Quiz, QuizAttempt
from app.repositories import courses_repo, enrollments_repo


class CourseNotFoundError(Exception):
    pass


class CourseNotPublishedError(Exception):
    pass


class AlreadyEnrolledError(Exception):
    pass


def list_student_courses(db: Session, student_id: int) -> list[dict]:
    rows = []

    for enrollment in enrollments_repo.list_student_enrollments(db, student_id):
        course = db.scalar(
            select(Course).where(
                Course.id == enrollment.course_id,
                Course.status == "PUBLISHED",
            )
        )
        if course is None:
            continue

        sections = list(db.scalars(
            select(Section)
            .where(Section.course_id == course.id)
            .order_by(Section.position.asc(), Section.id.asc())
        ).all())

        lessons = list(db.scalars(
            select(Lesson)
            .join(Section, Section.id == Lesson.section_id)
            .where(
                Section.course_id == course.id,
                Lesson.status == "PUBLISHED",
            )
            .order_by(Section.position.asc(), Lesson.position.asc(), Lesson.id.asc())
        ).all())

        lesson_ids = [lesson.id for lesson in lessons]
        completed_lesson_ids = set(
            db.scalars(
                select(LessonProgress.lesson_id).where(
                    LessonProgress.student_id == student_id,
                    LessonProgress.completed.is_(True),
                    LessonProgress.lesson_id.in_(lesson_ids),
                )
            ).all()
        ) if lesson_ids else set()

        unlocked_section_ids = []
        previous_section_passed = True
        passed_section_ids = set()

        for section in sections:
            if not previous_section_passed:
                break

            unlocked_section_ids.append(section.id)
            passed_attempt = db.scalar(
                select(QuizAttempt.id)
                .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
                .where(
                    Quiz.section_id == section.id,
                    Quiz.is_approved.is_(True),
                    QuizAttempt.student_id == student_id,
                    QuizAttempt.passed.is_(True),
                )
                .limit(1)
            )
            section_passed = passed_attempt is not None
            if section_passed:
                passed_section_ids.add(section.id)
            previous_section_passed = section_passed

        progress_percent = (
            round(len(completed_lesson_ids) * 100.0 / len(lessons), 2)
            if lessons else 0.0
        )

        resume_lesson = next(
            (
                lesson for lesson in lessons
                if lesson.section_id in unlocked_section_ids
                and lesson.id not in completed_lesson_ids
            ),
            None,
        )
        if resume_lesson is None and lessons:
            resume_lesson = lessons[0]

        all_sections_passed = bool(sections) and all(
            section.id in passed_section_ids for section in sections
        )
        learning_status = (
            "COMPLETED"
            if progress_percent >= 100.0 and all_sections_passed
            else "IN_PROGRESS"
            if completed_lesson_ids or progress_percent > 0
            else "NOT_STARTED"
        )

        rows.append({
            "course": {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "status": getattr(course.status, "value", course.status),
            },
            "status": learning_status,
            "progress_percent": progress_percent,
            "resume_lesson_id": resume_lesson.id if resume_lesson else None,
            "unlocked_section_ids": unlocked_section_ids,
        })

    return rows

# đăng ký khóa học
def enroll_course(
    db: Session,
    student_id: int,
    course_id: int,
) -> Enrollment:
    # Kiểm tra khóa học tồn tại
    course = courses_repo.get_course_by_id(db, course_id)

    if course is None:
        raise CourseNotFoundError()

    # Chỉ cho đăng ký khóa học đã xuất bản
    course_status = getattr(course.status, "value", course.status)

    if str(course_status).upper() != "PUBLISHED":
        raise CourseNotPublishedError()

    # Kiểm tra sinh viên đã đăng ký chưa
    existing = enrollments_repo.get_enrollment(
        db=db,
        student_id=student_id,
        course_id=course_id,
    )

    if existing is not None:
        raise AlreadyEnrolledError()

    # Tạo đăng ký
    try:
        return enrollments_repo.create_enrollment(
            db=db,
            student_id=student_id,
            course_id=course_id,
        )
    except IntegrityError as exc:
        # Có thể một request khác vừa đăng ký cùng lúc.
        raise AlreadyEnrolledError() from exc
