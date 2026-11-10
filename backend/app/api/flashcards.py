"""Flashcard APIs for published lessons and instructor review."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.flashcard import Flashcard
from app.models.lesson import Lesson
from app.models.section import Section
from app.models.user import User
from app.schemas.flashcard import (
    FlashcardCreateRequest,
    FlashcardResponse,
    FlashcardUpdateRequest,
)
from app.services import lesson_service

router = APIRouter(tags=["Flashcards"])


def _context(db: Session, lesson_id: int) -> tuple[Lesson, Section, Course] | None:
    return (
        db.query(Lesson, Section, Course)
        .join(Section, Lesson.section_id == Section.id)
        .join(Course, Section.course_id == Course.id)
        .filter(Lesson.id == lesson_id)
        .first()
    )


def _owned_context(
    db: Session, lesson_id: int, user: User,
) -> tuple[Lesson, Section, Course]:
    context = _context(db, lesson_id)
    if context is None:
        raise HTTPException(404, "Lesson not found.")
    lesson, section, course = context
    if str(user.role).upper() != "ADMIN" and course.instructor_id != user.id:
        raise HTTPException(403, "You do not own this course.")
    return lesson, section, course


@router.get("/lessons/{lesson_id}/flashcards")
def get_lesson_flashcards(
    lesson_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    context = _context(db, lesson_id)
    if context is None:
        raise HTTPException(404, "Lesson not found.")
    lesson, section, course = context

    role = str(user.role).upper()
    if role in ("STUDENT",):
        try:
            lesson_service.get_lesson_for_user(
                db, lesson_id, user_id=user.id, user_role=user.role,
            )
        except (
            lesson_service.LessonNotFoundError,
            lesson_service.SectionNotFoundError,
            lesson_service.CourseNotFoundError,
            lesson_service.CourseOwnershipError,
            lesson_service.PublishedCourseRequiredError,
            lesson_service.LessonAccessDeniedError,
        ) as exc:
            raise HTTPException(403, str(exc)) from exc
        enrolled = db.scalar(select(Enrollment.id).where(
            Enrollment.student_id == user.id,
            Enrollment.course_id == course.id,
        ))
        if enrolled is None:
            raise HTTPException(403, "Enrollment required.")
        cards = db.query(Flashcard).filter(
            Flashcard.lesson_id == lesson_id,
            Flashcard.is_approved.is_(True),
        ).order_by(Flashcard.position, Flashcard.id).all()
        publication_status = lesson.status
    else:
        lesson, section, course = _owned_context(db, lesson_id, user)
        cards = db.query(Flashcard).filter(
            Flashcard.lesson_id == lesson_id,
        ).order_by(Flashcard.position, Flashcard.id).all()
        publication_status = lesson.status

    values = [{
        "id": card.id,
        "front": card.front,
        "back": card.back,
        "position": card.position,
    } for card in cards]
    revision = hashlib.sha256(
        json.dumps(values, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "course_id": course.id,
        "section_id": section.id,
        "lesson_id": lesson.id,
        "publication_status": publication_status,
        "revision": revision,
        "cards": values,
    }


@router.post("/lessons/{lesson_id}/flashcards", response_model=FlashcardResponse, status_code=status.HTTP_201_CREATED)
def create_flashcard(
    lesson_id: int,
    payload: FlashcardCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lesson, _, _ = _owned_context(db, lesson_id, user)
    if str(user.role).upper() not in ("INSTRUCTOR", "ADMIN"):
        raise HTTPException(403, "Instructor role required.")
    card = Flashcard(
        lesson_id=lesson.id,
        front=payload.front,
        back=payload.back,
        position=payload.position,
        is_approved=False,
    )
    db.add(card)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Flashcard position is already in use.")
    db.refresh(card)
    return card


@router.put("/lessons/{lesson_id}/flashcards/{card_id}", response_model=FlashcardResponse)
def update_flashcard(
    lesson_id: int,
    card_id: int,
    payload: FlashcardUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lesson, _, _ = _owned_context(db, lesson_id, user)
    card = db.query(Flashcard).filter(
        Flashcard.id == card_id,
        Flashcard.lesson_id == lesson.id,
    ).first()
    if card is None:
        raise HTTPException(404, "Flashcard not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, field, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Flashcard position is already in use.")
    db.refresh(card)
    return card


@router.delete("/lessons/{lesson_id}/flashcards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flashcard(
    lesson_id: int,
    card_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lesson, _, _ = _owned_context(db, lesson_id, user)
    card = db.query(Flashcard).filter(
        Flashcard.id == card_id,
        Flashcard.lesson_id == lesson.id,
    ).first()
    if card is None:
        raise HTTPException(404, "Flashcard not found.")
    db.delete(card)
    db.commit()
    return None
