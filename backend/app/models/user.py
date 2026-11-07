from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, func, text

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('STUDENT', 'INSTRUCTOR', 'ADMIN')",
            name="ck_users_role",
        ),
    )

    id = Column(Integer, primary_key=True)
    cognito_sub = Column(String(255), unique=True, nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(320), unique=True, nullable=False)
    role = Column(
        String(20),
        nullable=False,
        default="STUDENT",
        server_default=text("'STUDENT'"),
    )
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())