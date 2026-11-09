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


def get_by_cognito_sub(db: Session, cognito_sub: str) -> User | None:
    return db.query(User).filter(User.cognito_sub == cognito_sub).first()


def create_cognito_user(
    db: Session,
    *,
    cognito_sub: str,
    name: str,
    email: str,
    role: str = "STUDENT",
) -> User:
    user = User(
        cognito_sub=cognito_sub,
        name=name,
        email=email.lower(),
        password_hash=None,
        role=role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyExists from exc
    db.refresh(user)
    return user
