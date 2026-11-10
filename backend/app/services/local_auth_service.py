"""Opt-in development/test auth against the application's configured database.

Mutations lock users first, serializing OTP replacement/consumption, login,
password changes and session revocation on PostgreSQL.
"""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import secrets
import smtplib

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
import jwt
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models.local_auth import LocalIdentity, LocalOTP, LocalSession
from app.models.user import User
from app.services.auth_service import AuthError, InvalidToken


password_hasher = PasswordHasher(type=Type.ID)
_dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))
_DELIVERY_MESSAGE = "Nếu email phù hợp, mã xác thực đã được gửi."


class LocalAuthError(AuthError):
    def __init__(self, message, code="LOCAL_AUTH_ERROR", status_code=400):
        super().__init__(message)
        self.message, self.code, self.status_code = message, code, status_code


def require_enabled():
    if not settings.LOCAL_AUTH_ENABLED or settings.APP_ENV not in {"development", "test"}:
        raise LocalAuthError("Local authentication is disabled.", "LOCAL_AUTH_DISABLED", 503)
    secret = settings.LOCAL_AUTH_JWT_SECRET
    value = secret.get_secret_value() if secret else ""
    if (len(value.encode()) < 32 or value.startswith("<")
            or not settings.LOCAL_AUTH_JWT_ISSUER or not settings.LOCAL_AUTH_JWT_AUDIENCE
            or settings.LOCAL_AUTH_JWT_ISSUER.startswith("https://cognito-idp.")):
        raise LocalAuthError("Local authentication is not configured.", "LOCAL_AUTH_NOT_CONFIGURED", 503)
    return value


def now():
    return datetime.now(timezone.utc)


def utc(value):
    # SQLite drops TZ info in unit tests; PostgreSQL returns aware timestamps.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _user(db, email):
    return (db.query(User).filter(func.lower(User.email) == email.lower())
            .populate_existing().with_for_update().first())


def _identity(db, user):
    if user is None or user.cognito_sub is not None or not user.password_hash:
        return None
    return (db.query(LocalIdentity).filter_by(user_id=user.id)
            .populate_existing().first())


def _password_matches(encoded, password):
    try:
        return password_hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def _otp_hash(user_id, purpose, nonce, code):
    return hmac.new(require_enabled().encode(),
                    f"otp:{user_id}:{purpose}:{nonce}:{code}".encode(), hashlib.sha256).hexdigest()


def _send_code(email, purpose, code):
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message["Subject"] = "LearnCloud - " + ("Verify email" if purpose == "verify" else "Reset password")
    message.set_content(
        f"Mã xác thực LearnCloud: {code}\n"
        f"Mã có hiệu lực trong {settings.LOCAL_AUTH_OTP_TTL_SECONDS} giây.\n"
        "Nếu bạn không yêu cầu mã này, hãy bỏ qua email."
    )
    # No debuglevel, logging, API echo or persistence of the clear code.
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise LocalAuthError("Email delivery unavailable. Please retry.", "EMAIL_UNAVAILABLE", 503) from None


def _issue_otp(db, user, purpose):
    current_time = now()
    otp = db.query(LocalOTP).filter_by(user_id=user.id, purpose=purpose).populate_existing().first()
    if otp and utc(otp.sent_at) + timedelta(seconds=settings.LOCAL_AUTH_RESEND_SECONDS) > current_time:
        raise LocalAuthError("Please wait before requesting another code.", "OTP_COOLDOWN", 429)
    if otp is None:
        otp = LocalOTP(user_id=user.id, purpose=purpose)
        db.add(otp)
    code = f"{secrets.randbelow(1_000_000):06d}"
    # Do not accidentally reissue the same value while the prior code is valid.
    while otp.nonce and hmac.compare_digest(otp.code_hash, _otp_hash(user.id, purpose, otp.nonce, code)):
        code = f"{secrets.randbelow(1_000_000):06d}"
    otp.nonce = secrets.token_hex(16)
    otp.code_hash = _otp_hash(user.id, purpose, otp.nonce, code)
    otp.sent_at = current_time
    otp.expires_at = current_time + timedelta(seconds=settings.LOCAL_AUTH_OTP_TTL_SECONDS)
    otp.attempts = 0
    otp.consumed_at = None
    _send_code(user.email, purpose, code)


def _delivery():
    return {"message": _DELIVERY_MESSAGE, "retry_after": settings.LOCAL_AUTH_RESEND_SECONDS}


def register(db, data):
    require_enabled()
    if _user(db, str(data.email)) is not None:
        raise LocalAuthError("Email is already registered. Use its original sign-in method.", "EMAIL_EXISTS", 409)
    user = User(name=data.name, email=str(data.email).lower(), role="STUDENT",
                password_hash=password_hasher.hash(data.password), cognito_sub=None)
    try:
        db.add(user)
        db.flush()
        db.add(LocalIdentity(user_id=user.id))
        _issue_otp(db, user, "verify")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise LocalAuthError("Email is already registered.", "EMAIL_EXISTS", 409) from None
    except LocalAuthError:
        db.rollback()
        raise
    return {**_delivery(), "verification_required": True}


def send_otp(db, email, purpose):
    require_enabled()
    user = _user(db, email)
    identity = _identity(db, user)
    eligible = identity and ((purpose == "verify" and identity.verified_at is None)
                             or (purpose == "reset" and identity.verified_at is not None))
    if eligible:
        try:
            _issue_otp(db, user, purpose)
            db.commit()
        except LocalAuthError:
            db.rollback()
            raise
    return _delivery()


def _consume_otp(db, user, purpose, code):
    otp = (db.query(LocalOTP).filter_by(user_id=user.id, purpose=purpose)
           .populate_existing().first()) if user else None
    if (otp is None or otp.consumed_at or utc(otp.expires_at) <= now()
            or otp.attempts >= settings.LOCAL_AUTH_OTP_MAX_ATTEMPTS):
        raise LocalAuthError("Invalid or expired verification code.", "INVALID_OTP")
    if not hmac.compare_digest(otp.code_hash, _otp_hash(user.id, purpose, otp.nonce, code)):
        otp.attempts += 1
        db.commit()  # Persist failed guesses even though this request is rejected.
        raise LocalAuthError("Invalid or expired verification code.", "INVALID_OTP")
    otp.consumed_at = now()


def verify_email(db, email, code):
    require_enabled()
    user = _user(db, email)
    identity = _identity(db, user)
    if identity is None or identity.verified_at:
        raise LocalAuthError("Invalid or expired verification code.", "INVALID_OTP")
    _consume_otp(db, user, "verify", code)
    identity.verified_at = now()
    db.commit()
    return {"message": "Đã xác minh email."}


def login(db, email, password):
    secret = require_enabled()
    user = _user(db, email)
    identity = _identity(db, user)
    if identity and identity.locked_until and utc(identity.locked_until) > now():
        raise LocalAuthError("Too many attempts. Try again later.", "LOGIN_LOCKED", 429)
    matches = _password_matches(user.password_hash if identity else _dummy_password_hash, password)
    if not identity or not matches:
        if identity:
            identity.login_failures += 1
            if identity.login_failures >= settings.LOCAL_AUTH_LOGIN_MAX_ATTEMPTS:
                identity.locked_until = now() + timedelta(seconds=settings.LOCAL_AUTH_LOGIN_LOCK_SECONDS)
                identity.login_failures = 0
            db.commit()
        raise LocalAuthError("Invalid email or password.", "INVALID_CREDENTIALS", 401)
    if identity.verified_at is None:
        raise LocalAuthError("Verify your email before signing in.", "UserNotConfirmedException", 403)
    identity.login_failures = 0
    identity.locked_until = None
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(password)
    current_time = now()
    expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    expires_at = current_time + timedelta(seconds=expires_in)
    jti = secrets.token_urlsafe(32)
    token = jwt.encode({
        "sub": str(user.id), "jti": jti, "iat": current_time, "exp": expires_at,
        "iss": settings.LOCAL_AUTH_JWT_ISSUER, "aud": settings.LOCAL_AUTH_JWT_AUDIENCE,
        "token_use": "access", "auth_provider": "local",
    }, secret, algorithm="HS256")
    db.add(LocalSession(token_hash=hashlib.sha256(jti.encode()).hexdigest(),
                        user_id=user.id, expires_at=expires_at))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}


def _validated_session(db, token):
    try:
        secret = require_enabled()
        claims = jwt.decode(token, secret, algorithms=["HS256"],
                            issuer=settings.LOCAL_AUTH_JWT_ISSUER,
                            audience=settings.LOCAL_AUTH_JWT_AUDIENCE,
                            options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]})
        if claims.get("token_use") != "access" or claims.get("auth_provider") != "local":
            raise InvalidToken()
        user_id = int(claims["sub"])
        session = (db.query(LocalSession).filter_by(
            token_hash=hashlib.sha256(claims["jti"].encode()).hexdigest(), user_id=user_id)
            .populate_existing().first())
        if not session or session.revoked_at or utc(session.expires_at) <= now():
            raise InvalidToken()
        user = db.query(User).filter_by(id=user_id).populate_existing().first()
        identity = _identity(db, user)
        if identity is None or identity.verified_at is None:
            raise InvalidToken()
        return user, session
    except (LocalAuthError, jwt.PyJWTError, ValueError, TypeError, AttributeError):
        raise InvalidToken() from None


def user_from_access_token(db, token):
    return _validated_session(db, token)[0]


def logout(db, token):
    user, _ = _validated_session(db, token)
    # Serialize with password reset/change, which revoke all sessions.
    db.query(User).filter_by(id=user.id).with_for_update().first()
    _, session = _validated_session(db, token)
    session.revoked_at = now()
    db.commit()
    return {"message": "Signed out."}


def _revoke_sessions(db, user_id):
    db.query(LocalSession).filter_by(user_id=user_id, revoked_at=None).update({"revoked_at": now()})


def reset_password(db, email, code, password):
    require_enabled()
    user = _user(db, email)
    identity = _identity(db, user)
    if identity is None or identity.verified_at is None:
        raise LocalAuthError("Invalid or expired verification code.", "INVALID_OTP")
    _consume_otp(db, user, "reset", code)
    user.password_hash = password_hasher.hash(password)
    identity.login_failures, identity.locked_until = 0, None
    _revoke_sessions(db, user.id)
    db.commit()
    return {"message": "Đã đặt lại mật khẩu."}


def change_password(db, token, current_password, new_password):
    user, _ = _validated_session(db, token)
    user = db.query(User).filter_by(id=user.id).populate_existing().with_for_update().one()
    _validated_session(db, token)
    if not _password_matches(user.password_hash, current_password):
        raise LocalAuthError("Invalid current password.", "INVALID_CREDENTIALS", 400)
    user.password_hash = password_hasher.hash(new_password)
    # A previously issued recovery code must not undo an authenticated change.
    db.query(LocalOTP).filter_by(user_id=user.id, purpose="reset").update({"consumed_at": now()})
    _revoke_sessions(db, user.id)
    db.commit()
    return {"message": "Password changed. Sign in again."}
