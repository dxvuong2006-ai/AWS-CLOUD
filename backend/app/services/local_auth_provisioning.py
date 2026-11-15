"""Operator-only enrollment. Intentionally has no HTTP router or email path."""
import re

from sqlalchemy import func, text

from app.models.local_auth import LocalIdentity
from app.models.user import User
from app.services import local_auth_service as auth


PROVISIONER_ROLE = "learncloud_local_auth_provisioner"
MIGRATION_DESCRIPTION = "Explicit operator provisioning of existing local auth identities"


class ProvisioningError(Exception):
    pass


def require_operator(db):
    if db.get_bind().dialect.name != "postgresql":
        raise ProvisioningError("Provisioning requires PostgreSQL server authorization.")
    actor = db.execute(text("""
        SELECT session_user::text AS operator, current_user::text AS effective_user,
               EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
                       WHERE r.rolname=:role
                         AND pg_catalog.pg_has_role(session_user,r.oid,'MEMBER')) AS authorized
    """), {"role": PROVISIONER_ROLE}).mappings().one()
    if not actor["authorized"] or actor["operator"] != actor["effective_user"]:
        raise ProvisioningError("A directly authenticated DBA-authorized provisioning login is required.")
    return actor["operator"]


def _schema_ready(db):
    ready = db.execute(text("""
        SELECT to_regclass('public.local_auth_identities') IS NOT NULL
           AND to_regclass('public.local_auth_otps') IS NOT NULL
           AND to_regclass('public.local_auth_sessions') IS NOT NULL
           AND to_regclass('public.schema_migrations') IS NOT NULL AS ready
    """)).scalar_one()
    if not ready:
        raise ProvisioningError("Review/apply migrations 0007 and 0008 before provisioning.")
    version = db.execute(text("SELECT description FROM public.schema_migrations WHERE version='0008'")).scalar_one_or_none()
    if version != MIGRATION_DESCRIPTION:
        raise ProvisioningError("Migration 0008 is missing or conflicts with a different change.")


def inspect_target(db, *, user_id, expected_email, expected_role, expected_cognito_sub, lock=False):
    auth.require_enabled()
    operator = require_operator(db)
    _schema_ready(db)
    query = db.query(User).filter(User.id == user_id).populate_existing()
    user = (query.with_for_update() if lock else query).one_or_none()
    if user is None:
        raise ProvisioningError("The selected user ID does not exist; no user will be created.")
    if (user.email != expected_email or user.role != expected_role
            or user.cognito_sub != expected_cognito_sub):
        raise ProvisioningError("User ID/email/role/Cognito subject do not match the reviewed target.")
    if user.role not in {"INSTRUCTOR", "ADMIN"}:
        raise ProvisioningError("This procedure only enrolls existing Instructor/Admin accounts.")
    if db.query(User.id).filter(func.lower(User.email) == user.email.lower()).count() != 1:
        raise ProvisioningError("Email login is ambiguous across existing users; resolve through a separate review.")
    if db.query(LocalIdentity).filter_by(user_id=user.id).first() is not None or user.password_hash is not None:
        raise ProvisioningError("A local identity or password already exists; refusing to overwrite credentials.")
    return user, operator


def provision(db, *, user_id, expected_email, expected_role, expected_cognito_sub, password, approval_reference):
    # Authorization/preconditions are enforced here, not only in the CLI.
    user, operator = inspect_target(db, user_id=user_id, expected_email=expected_email,
        expected_role=expected_role, expected_cognito_sub=expected_cognito_sub, lock=True)
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ProvisioningError("Use a local password of 12-128 characters.")
    if not isinstance(approval_reference, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}", approval_reference):
        raise ProvisioningError("Supply a reviewed approval/ticket reference (3-128 safe characters).")
    user.password_hash = auth.password_hasher.hash(password)
    timestamp = auth.now()
    db.add(LocalIdentity(user_id=user.id, verified_at=timestamp, provisioned_at=timestamp,
                         provisioned_by=operator, provisioning_reference=approval_reference,
                         login_failures=0))
    # The caller owns COMMIT/ROLLBACK. No users INSERT or identity/role rebinding.
    db.flush()
    return {"user_id": user.id, "role": user.role, "provisioned_by": operator,
            "approval_reference": approval_reference}
