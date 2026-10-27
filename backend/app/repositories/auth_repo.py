import uuid

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User


class EmailAlreadyExists(Exception):
    pass


def get_by_email(db: Session, email: str) -> User | None:
    # Covers previously seeded records that have a mixed-case email.
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create_student(db: Session, *, name: str, email: str, password_hash: str) -> User:
    # Preserve legacy NOT NULL cognito_sub without pretending to be Cognito.
    user = User(
        cognito_sub=f"local:{uuid.uuid4()}",
        name=name,
        email=email.lower(),
        password_hash=password_hash,
        role="STUDENT",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyExists from exc
    db.refresh(user)
    return user
