from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.auth import (RegisterRequest, LoginRequest, VerifyEmailRequest,
                              ResendVerificationRequest, ForgotPasswordRequest,
                              ResetPasswordRequest, ChangePasswordRequest)
from app.services import local_auth_service as service
from app.services.auth_service import InvalidToken


def _enabled():
    try:
        service.require_enabled()
    except service.LocalAuthError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from None


router = APIRouter(prefix="/auth/local", tags=["Local authentication"],
                   dependencies=[Depends(_enabled)])
bearer = HTTPBearer(auto_error=False)


def _call(action, *args):
    try:
        return action(*args)
    except service.LocalAuthError as exc:
        headers = {"Retry-After": str(service.settings.LOCAL_AUTH_RESEND_SECONDS)} if exc.code == "OTP_COOLDOWN" else None
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message},
                            headers=headers) from None
    except InvalidToken:
        raise HTTPException(401, detail="Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"}) from None


def _token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return _call(service.register, db, payload)


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    return _call(service.verify_email, db, str(payload.email).lower(), payload.code)


@router.post("/resend-verification")
def resend(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    return _call(service.send_otp, db, str(payload.email).lower(), "verify")


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return _call(service.login, db, str(payload.email).lower(), payload.password)


@router.post("/logout")
def logout(token: str = Depends(_token), db: Session = Depends(get_db)):
    return _call(service.logout, db, token)


@router.post("/forgot-password")
def forgot(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return _call(service.send_otp, db, str(payload.email).lower(), "reset")


@router.post("/reset-password")
def reset(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    return _call(service.reset_password, db, str(payload.email).lower(), payload.code, payload.password)


@router.post("/change-password")
def change(payload: ChangePasswordRequest, token: str = Depends(_token), db: Session = Depends(get_db)):
    return _call(service.change_password, db, token, payload.current_password, payload.new_password)
