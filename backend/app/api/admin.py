from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.user import User
from app.services.auth_service import hash_password

router = APIRouter(prefix="/admin", tags=["Administration"])


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    role: str
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    role: str


def _public(user):
    return {"id": user.id, "name": user.name, "email": user.email,
            "role": user.role, "status": "ACTIVE"}


def _validate_role(role):
    if role not in {"INSTRUCTOR", "ADMIN"}:
        raise HTTPException(422, "Admin can create only instructor or admin accounts.")


@router.get("/users")
def list_users(search: str = Query("", max_length=120),
               db: Session = Depends(get_db), _admin=Depends(require_admin)):
    query = db.query(User)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter((User.name.ilike(term)) | (User.email.ilike(term)))
    return [_public(user) for user in query.order_by(User.id).all()]


@router.post("/users", status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                _admin=Depends(require_admin)):
    _validate_role(payload.role)
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(409, "Email đã được sử dụng.")
    user = User(name=payload.name.strip(), email=payload.email.lower(),
                role=payload.role, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {**_public(user), "temporary_password": payload.password}


@router.patch("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                _admin=Depends(require_admin)):
    _validate_role(payload.role)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Không tìm thấy tài khoản.")
    duplicate = db.query(User).filter(User.email == payload.email.lower(),
                                      User.id != user_id).first()
    if duplicate:
        raise HTTPException(409, "Email đã được sử dụng.")
    user.name, user.email, user.role = payload.name.strip(), payload.email.lower(), payload.role
    db.commit()
    db.refresh(user)
    return _public(user)
