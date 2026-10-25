from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    # Public sign-up is STUDENT only. Instructor/Admin must be provisioned by an admin.
    try:
        return auth_service.register_student(db, payload)
    except auth_service.DuplicateEmail as exc:
        raise HTTPException(status_code=409, detail="Email is already registered") from exc


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate(db, email=str(payload.email), password=payload.password)
    except auth_service.InvalidCredentials as exc:
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc
    access_token, expires_in = auth_service.issue_access_token(user)
    return TokenResponse(access_token=access_token, expires_in=expires_in, user=user)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
