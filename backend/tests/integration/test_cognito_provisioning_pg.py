"""Cognito provisioning against an explicitly isolated PostgreSQL 16 database.

No test in this module creates an AWS client. The database URL guard is checked
before SQLAlchemy constructs an engine.
"""

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from unittest.mock import Mock
from uuid import uuid4

from botocore.exceptions import ClientError
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.services import auth_service


LIVE = os.environ.get("LEARNCLOUD_RUN_AUTH_DB_TESTS") == "1"


def isolated_url(value: str):
    url = make_url(value)
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg2"}
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.database != "learncloud_auth_test"
        or url.username != "learncloud_auth_test"
        or not set(url.query).issubset({"connect_timeout", "application_name"})
    ):
        raise RuntimeError(
            "Only the isolated local learncloud_auth_test database/user is permitted"
        )
    return url


@pytest.fixture(scope="module")
def pg_engine():
    if not LIVE:
        pytest.skip("Set LEARNCLOUD_RUN_AUTH_DB_TESTS=1 for isolated PostgreSQL")
    url = isolated_url(os.environ["LEARNCLOUD_AUTH_TEST_DATABASE_URL"])
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "learncloud_auth_test"
            server_version = int(connection.scalar(text("SHOW server_version_num")))
            assert 160000 <= server_version < 170000
            assert connection.scalar(
                text("SELECT version FROM schema_migrations WHERE version='0007'")
            ) == "0007"
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_db(pg_engine):
    with pg_engine.connect() as connection:
        outer = connection.begin()
        db = Session(
            bind=connection,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield db
        finally:
            db.close()
            outer.rollback()


@pytest.fixture(autouse=True)
def cognito_settings(monkeypatch):
    monkeypatch.setattr(settings, "COGNITO_REGION", "ap-southeast-1")
    monkeypatch.setattr(settings, "COGNITO_USER_POOL_ID", "ap-southeast-1_testpool")
    monkeypatch.setattr(settings, "COGNITO_APP_CLIENT_ID", "test-client")


def claims(sub: str, username: str):
    return {
        "sub": sub,
        "username": username,
        "token_use": "access",
        "client_id": "test-client",
        "iss": (
            "https://cognito-idp.ap-southeast-1.amazonaws.com/"
            "ap-southeast-1_testpool"
        ),
    }


def cognito_profile(
    sub: str,
    email: str,
    *,
    status: str = "CONFIRMED",
    email_verified: bool = True,
    enabled: bool = True,
):
    return {
        "Enabled": enabled,
        "UserStatus": status,
        "UserAttributes": [
            {"Name": "sub", "Value": sub},
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": str(email_verified).lower()},
            {"Name": "name", "Value": "PostgreSQL student"},
        ],
    }


def test_pg_first_login_provisions_once(pg_db, monkeypatch):
    suffix = uuid4().hex
    sub = f"pg-first-{suffix}"
    email = f"pg-first-{suffix}@example.com"
    client = Mock()
    client.admin_get_user.return_value = cognito_profile(sub, email)
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)

    first = auth_service.sync_authorizer_claims(pg_db, claims(sub, f"username-{suffix}"))
    second = auth_service.sync_authorizer_claims(pg_db, claims(sub, f"username-{suffix}"))

    assert first.id == second.id
    assert (first.email, first.role) == (email, "STUDENT")
    assert pg_db.scalar(select(func.count()).select_from(User).where(User.cognito_sub == sub)) == 1
    client.admin_get_user.assert_called_once()


def test_pg_verify_retry_repairs_confirmed_identity(pg_db, monkeypatch):
    suffix = uuid4().hex
    sub = f"pg-verify-{suffix}"
    email = f"pg-verify-{suffix}@example.com"
    client = Mock()
    client.confirm_sign_up.side_effect = ClientError(
        {
            "Error": {
                "Code": "NotAuthorizedException",
                "Message": "Current status is CONFIRMED",
            }
        },
        "ConfirmSignUp",
    )
    client.admin_get_user.return_value = cognito_profile(sub, email)
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)

    auth_service.verify_email(pg_db, email, "123456")
    user = pg_db.scalar(select(User).where(User.cognito_sub == sub))
    user.name = "RDS authoritative name"
    user.role = "INSTRUCTOR"
    pg_db.commit()
    auth_service.verify_email(pg_db, email, "123456")

    pg_db.refresh(user)
    assert (user.name, user.role) == ("RDS authoritative name", "INSTRUCTOR")
    assert pg_db.scalar(select(func.count()).select_from(User).where(User.cognito_sub == sub)) == 1


def test_pg_email_conflict_does_not_rebind(pg_db):
    suffix = uuid4().hex
    email = f"pg-email-conflict-{suffix}@example.com"
    existing = User(
        cognito_sub=f"old-sub-{suffix}",
        name="Existing owner",
        email=email,
        role="ADMIN",
    )
    pg_db.add(existing)
    pg_db.commit()

    with pytest.raises(auth_service.IdentityConflict):
        auth_service.ensure_cognito_profile(
            pg_db,
            {"sub": f"new-sub-{suffix}", "email": email, "name": "New identity"},
        )

    pg_db.refresh(existing)
    assert (existing.cognito_sub, existing.name, existing.role) == (
        f"old-sub-{suffix}",
        "Existing owner",
        "ADMIN",
    )


def test_pg_subject_and_email_cross_conflict_changes_neither_row(pg_db):
    suffix = uuid4().hex
    subject_owner = User(
        cognito_sub=f"shared-sub-{suffix}",
        name="Subject owner",
        email=f"subject-{suffix}@example.com",
        role="INSTRUCTOR",
    )
    email_owner = User(
        cognito_sub=f"other-sub-{suffix}",
        name="Email owner",
        email=f"email-{suffix}@example.com",
        role="ADMIN",
    )
    pg_db.add_all([subject_owner, email_owner])
    pg_db.commit()

    with pytest.raises(auth_service.IdentityConflict):
        auth_service.ensure_cognito_profile(
            pg_db,
            {
                "sub": subject_owner.cognito_sub,
                "email": email_owner.email,
                "name": "Conflicting identity",
            },
        )

    pg_db.refresh(subject_owner)
    pg_db.refresh(email_owner)
    assert (subject_owner.name, subject_owner.role) == ("Subject owner", "INSTRUCTOR")
    assert (email_owner.name, email_owner.role) == ("Email owner", "ADMIN")


@pytest.mark.parametrize(
    "profile",
    [
        cognito_profile(
            "pg-blocked-sub", "pg-blocked@example.com", email_verified=False
        ),
        cognito_profile(
            "pg-blocked-sub",
            "pg-blocked@example.com",
            status="FORCE_CHANGE_PASSWORD",
        ),
    ],
    ids=["email-unverified", "force-change-password"],
)
def test_pg_unprovisionable_cognito_state_creates_no_row(
    pg_db, monkeypatch, profile
):
    suffix = uuid4().hex
    profile["UserAttributes"][0]["Value"] = f"pg-blocked-{suffix}"
    profile["UserAttributes"][1]["Value"] = f"pg-blocked-{suffix}@example.com"
    client = Mock()
    client.admin_get_user.return_value = profile
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)

    with pytest.raises(auth_service.InvalidToken):
        auth_service.sync_authorizer_claims(
            pg_db,
            claims(f"pg-blocked-{suffix}", f"blocked-username-{suffix}"),
        )

    assert pg_db.scalar(
        select(func.count()).select_from(User).where(User.cognito_sub == f"pg-blocked-{suffix}")
    ) == 0


def test_pg_concurrent_first_login_is_idempotent(pg_engine):
    suffix = uuid4().hex
    identity = {
        "sub": f"pg-race-{suffix}",
        "email": f"pg-race-{suffix}@example.com",
        "name": "Concurrent student",
    }
    workers = 8
    barrier = Barrier(workers)

    def provision():
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            return auth_service.ensure_cognito_profile(db, identity).id

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            ids = list(executor.map(lambda _: provision(), range(workers)))
        assert len(set(ids)) == 1
        with Session(pg_engine) as db:
            assert db.scalar(
                select(func.count()).select_from(User).where(User.cognito_sub == identity["sub"])
            ) == 1
    finally:
        with pg_engine.begin() as connection:
            connection.execute(
                User.__table__.delete().where(User.cognito_sub == identity["sub"])
            )


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://learncloud_auth_test@production.example.com/learncloud_auth_test",
        "postgresql://learncloud_auth_test@127.0.0.1/learncloud",
        "postgresql://other@127.0.0.1/learncloud_auth_test",
        "postgresql://learncloud_auth_test@127.0.0.1/learncloud_auth_test?host=prod.example.com",
    ],
)
def test_pg_guard_refuses_non_isolated_targets(value):
    with pytest.raises(RuntimeError):
        isolated_url(value)
