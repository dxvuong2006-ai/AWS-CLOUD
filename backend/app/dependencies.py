from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User


def get_db():
    """Cung cấp Session và đóng lại sau khi xử lý yêu cầu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    x_demo_user: str = Header(default="1", alias="X-Demo-User"),
    db: Session = Depends(get_db),
) -> User:
    """Xác định người dùng demo theo mã ID trong header."""
    try:
        user_id = int(x_demo_user)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="X-Demo-User must be a numeric user ID.",
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Demo user not found.")
    return user


def require_student(user: User = Depends(get_current_user)) -> User:
    """Chỉ cho phép người dùng có vai trò học viên."""
    if str(getattr(user, "role", "")).upper() != "STUDENT":
        raise HTTPException(status_code=403, detail="Student role required.")
    return user


def require_instructor(user: User = Depends(get_current_user)) -> User:
    """Chỉ cho phép người dùng có vai trò giảng viên."""
    if str(getattr(user, "role", "")).upper() != "INSTRUCTOR":
        raise HTTPException(status_code=403, detail="Instructor role required.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Chỉ cho phép người dùng có vai trò quản trị viên."""
    if str(getattr(user, "role", "")).upper() != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
