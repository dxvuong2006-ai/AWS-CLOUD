from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.models.video_pipeline import VideoPipelineRun
from app.schemas.auth import (
    AdminUserCreateRequest,
    AdminUserStatusRequest,
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
    changes = payload.model_dump(exclude_unset=True)
    if "role" in changes:
        if changes["role"] is None:
            raise HTTPException(422, "Role must not be null")
        # Serialize role changes across PostgreSQL workers, not just a count
        # outside a transaction. Always lock the admin set in the same order.
        admins = list(db.scalars(
            select(User).where(User.role == "ADMIN").order_by(User.id)
            .with_for_update().execution_options(populate_existing=True)
        ).all())
        # The caller may have been demoted while waiting for these locks.
        if not any(user.id == _admin.id for user in admins):
            db.rollback()
            raise HTTPException(403, "Admin role required")
        user = db.scalar(
            select(User).where(User.id == user_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        active_admins = [admin for admin in admins if admin.status == "ACTIVE"]
        if (user is not None and user.status == "ACTIVE" and user.role == "ADMIN"
                and changes["role"] != "ADMIN" and len(active_admins) < 2):
            db.rollback()
            raise HTTPException(409, "Cannot demote the last admin")
    else:
        user = db.get(User, user_id)
    if user is None:
        db.rollback()
        raise HTTPException(404, "User not found")
    old_role = user.role
    old_email = user.email
    if not user.cognito_sub and "email" in changes and str(changes["email"]).lower() != old_email.lower():
        db.rollback()
        raise HTTPException(409, "Local login email changes require a separate ownership verification flow")
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"]).lower()
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(422, "Name must not be blank")
    for key, value in changes.items():
        setattr(user, key, value)
    try:
        if user.cognito_sub:
            auth_service.admin_update_profile(
                cognito_sub=user.cognito_sub,
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
    if "role" in changes and user.cognito_sub:
        try:
            auth_service.admin_update_role(
                cognito_sub=user.cognito_sub or "",
                email=user.email,
                old_role=old_role,
                new_role=changes["role"],
            )
        except auth_service.CognitoAuthError as exc:
            db.rollback()
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


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def set_user_status(
    user_id: int,
    payload: AdminUserStatusRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    enabled = payload.enabled

    # Lock the admin cohort in a stable order. This serializes concurrent
    # account disables with role demotions and preserves one active admin.
    admins = list(db.scalars(
        select(User).where(User.role == "ADMIN").order_by(User.id)
        .with_for_update().execution_options(populate_existing=True)
    ).all())
    if not any(user.id == _admin.id and user.status == "ACTIVE" for user in admins):
        db.rollback()
        raise HTTPException(403, "Active admin role required")
    user = db.scalar(
        select(User).where(User.id == user_id).with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        db.rollback()
        raise HTTPException(404, "User not found")
    if user.id == _admin.id and not enabled:
        db.rollback()
        raise HTTPException(409, "You cannot disable your own account")
    active_admins = [admin for admin in admins if admin.status == "ACTIVE"]
    if (not enabled and user.status == "ACTIVE" and user.role == "ADMIN"
            and len(active_admins) <= 1):
        db.rollback()
        raise HTTPException(409, "Cannot disable the last active admin")

    old_status = user.status
    new_status = "ACTIVE" if enabled else "INACTIVE"
    try:
        if user.cognito_sub:
            auth_service.admin_set_user_enabled(email=user.email, enabled=enabled)
    except auth_service.CognitoAuthError as exc:
        db.rollback()
        if user.cognito_sub:
            try:
                # Cognito timeouts can be ambiguous: the remote operation may
                # have completed even though its response did not arrive.
                auth_service.admin_set_user_enabled(
                    email=user.email, enabled=(old_status == "ACTIVE")
                )
            except Exception as rollback_exc:
                raise HTTPException(
                    502,
                    detail={
                        "code": "ACCOUNT_SYNC_INCONSISTENT",
                        "message": "Cognito status could not be confirmed or restored; reconcile both stores.",
                    },
                ) from rollback_exc
        raise HTTPException(
            exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    user.status = new_status
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        if user.cognito_sub:
            try:
                auth_service.admin_set_user_enabled(
                    email=user.email, enabled=(old_status == "ACTIVE")
                )
            except Exception as rollback_exc:
                raise HTTPException(
                    502,
                    detail={
                        "code": "ACCOUNT_SYNC_INCONSISTENT",
                        "message": "Account status could not be saved and Cognito rollback failed; reconcile both stores.",
                    },
                ) from rollback_exc
        raise HTTPException(500, "Account status could not be saved") from exc
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
