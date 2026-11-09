from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.models.video_pipeline import VideoPipelineRun
from app.schemas.auth import (
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=list[UserResponse])
def list_users(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    statement = select(User).order_by(User.created_at.desc(), User.id.desc())
    if search:
        needle = f"%{search.strip().lower()}%"
        statement = statement.where(
            func.lower(User.name).like(needle) | func.lower(User.email).like(needle)
        )
    return list(db.scalars(statement).all())


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    email = str(payload.email).lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Email is already registered")
    try:
        cognito_sub = auth_service.admin_create_user(
            name=payload.name,
            email=email,
            password=payload.password,
            role=payload.role,
        )
    except auth_service.CognitoAuthError as exc:
        raise HTTPException(
            exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    user = User(cognito_sub=cognito_sub, name=payload.name.strip(), email=email, role=payload.role, password_hash=None)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Email is already registered") from exc
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    changes = payload.model_dump(exclude_unset=True)
    old_role = user.role
    old_email = user.email
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"]).lower()
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(422, "Name must not be blank")
    for key, value in changes.items():
        setattr(user, key, value)
    try:
        auth_service.admin_update_profile(
            cognito_sub=user.cognito_sub or "",
            email=old_email,
            name=changes.get("name"),
            new_email=changes.get("email"),
        )
    except auth_service.CognitoAuthError as exc:
        db.rollback()
        raise HTTPException(
            exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    if "role" in changes:
        try:
            auth_service.admin_update_role(
                cognito_sub=user.cognito_sub or "",
                email=user.email,
                old_role=old_role,
                new_role=changes["role"],
            )
        except auth_service.CognitoAuthError as exc:
            raise HTTPException(
                exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Email is already registered") from exc
    db.refresh(user)
    return user


@router.get("/monitoring/jobs")
def list_monitoring_jobs(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    runs = db.scalars(
        select(VideoPipelineRun).order_by(
            VideoPipelineRun.updated_at.desc(), VideoPipelineRun.id.desc()
        ).limit(50)
    ).all()
    return [
        {
            "id": run.id,
            "lesson_id": run.lesson_id,
            "stage": "Video pipeline",
            "status": "FAILED" if run.state == "FAILED" else "SUCCEEDED" if run.state == "COMPLETE" else "RUNNING",
            "state": run.state,
            "error_code": run.error_code,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        }
        for run in runs
    ]
