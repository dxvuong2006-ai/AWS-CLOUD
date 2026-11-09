from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)


def cognito_http_error(exc: auth_service.CognitoAuthError):
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    ) from exc


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        return auth_service.register_student(db, payload)
    except auth_service.CognitoAuthError as exc:
        cognito_http_error(exc)


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    try:
        return auth_service.verify_email(db, str(payload.email).lower(), payload.code)
    except auth_service.CognitoAuthError as exc:
        cognito_http_error(exc)


@router.post("/resend-verification")
def resend_verification(payload: ResendVerificationRequest):
    try:
        return auth_service.resend_verification(str(payload.email).lower())
    except auth_service.CognitoAuthError as exc:
        cognito_http_error(exc)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    try:
        return auth_service.forgot_password(str(payload.email).lower())
    except auth_service.CognitoAuthError as exc:
        cognito_http_error(exc)


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    try:
        return auth_service.reset_password(
            str(payload.email).lower(),
            payload.code,
            payload.password,
        )
    except auth_service.CognitoAuthError as exc:
        cognito_http_error(exc)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_profile(
    payload: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.name = payload.name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return auth_service.change_password(
            credentials.credentials,
            payload.current_password,
            payload.new_password,
        )
    except auth_service.CognitoAuthError as exc:
        cognito_http_error(exc)
