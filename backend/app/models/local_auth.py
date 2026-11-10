"""Local identity metadata is separate from users; legacy hashes are not opt-in."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class LocalIdentity(Base):
    __tablename__ = "local_auth_identities"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    login_failures = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)


class LocalOTP(Base):
    __tablename__ = "local_auth_otps"
    __table_args__ = (
        CheckConstraint("purpose IN ('verify', 'reset')", name="ck_local_otp_purpose"),
    )

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    purpose = Column(String(10), primary_key=True)
    code_hash = Column(String(64), nullable=False)
    nonce = Column(String(64), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)


class LocalSession(Base):
    __tablename__ = "local_auth_sessions"

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
