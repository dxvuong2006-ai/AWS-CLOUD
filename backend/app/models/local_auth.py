"""Local identity metadata is separate from users; legacy hashes are not opt-in."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class LocalIdentity(Base):
    __tablename__ = "local_auth_identities"
    __table_args__ = (
        CheckConstraint(
            "(provisioned_at IS NULL AND provisioned_by IS NULL AND provisioning_reference IS NULL) OR "
            "(provisioned_at IS NOT NULL AND provisioned_by IS NOT NULL AND provisioning_reference IS NOT NULL "
            "AND verified_at IS NOT NULL AND length(trim(provisioned_by)) > 0 "
            "AND length(trim(provisioning_reference)) > 0)",
            name="ck_local_identity_provisioning",
        ),
    )

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    login_failures = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    # Explicit operator enrollment; never populated by signup/email OTP.
    provisioned_at = Column(DateTime(timezone=True), nullable=True)
    provisioned_by = Column(String(63), nullable=True)
    provisioning_reference = Column(String(128), nullable=True)


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
