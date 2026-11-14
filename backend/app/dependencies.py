from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.services import auth_service

bearer = HTTPBearer(auto_error=False)


def get_db():
    """Cung cấp Session và đóng lại sau khi xử lý yêu cầu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    event = request.scope.get("aws.event")
    if event is None:
        extensions = request.scope.get("extensions")
        if isinstance(extensions, dict):
            event = extensions.get("aws.event")

    claims = auth_service.authorizer_claims_from_event(event)
    if claims is not None:
        try:
            return auth_service.sync_authorizer_claims(
                db, claims,
                access_token=credentials.credentials if credentials else None,
            )
        except auth_service.CognitoAuthError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except auth_service.InvalidToken as exc:
            raise HTTPException(status_code=401, detail="Authentication required",
                                headers={"WWW-Authenticate": "Bearer"}) from exc

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        return auth_service.user_from_access_token(db, credentials.credentials)
    except auth_service.InvalidToken as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"}) from exc
    except auth_service.CognitoAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


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
