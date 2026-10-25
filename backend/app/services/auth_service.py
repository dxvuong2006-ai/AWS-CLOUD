from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.orm import Session

from app.config import settings
from app.repositories import auth_repo
from app.schemas.auth import RegisterRequest

# Passwords are only stored as Argon2id hashes; no plaintext storage.
_password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_ALGORITHM = "HS256"
_ISSUER = "learncloud"
_AUDIENCE = "learncloud-api"


class AuthError(Exception):
    pass


class InvalidCredentials(AuthError):
    pass


class InvalidToken(AuthError):
    pass


class DuplicateEmail(AuthError):
    pass


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def register_student(db: Session, data: RegisterRequest):
    email = str(data.email).lower()
    if auth_repo.get_by_email(db, email):
        raise DuplicateEmail()
    try:
        return auth_repo.create_student(
            db, name=data.name, email=email, password_hash=hash_password(data.password)
        )
    except auth_repo.EmailAlreadyExists as exc:
        raise DuplicateEmail() from exc


def authenticate(db: Session, *, email: str, password: str):
    user = auth_repo.get_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return user


def issue_access_token(user) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    lifetime = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    payload = {
        "sub": str(user.id),
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=lifetime),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=_ALGORITHM)
    return token, lifetime * 60


def user_from_access_token(db: Session, token: str):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[_ALGORITHM],
            issuer=_ISSUER,
            audience=_AUDIENCE,
            options={"require": ["sub", "iss", "aud", "iat", "exp"]},
        )
        subject = payload["sub"]
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
            raise InvalidToken()
        user = auth_repo.get_by_id(db, int(subject))
        if user is None:
            raise InvalidToken()
        return user
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise InvalidToken() from exc
