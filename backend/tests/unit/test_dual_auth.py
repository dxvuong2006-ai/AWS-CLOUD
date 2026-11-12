"""Real service/JWT/guards tests. Optional real PostgreSQL + Mailpit transport.

By default SQLite + captured SMTP. For the opt-in run, only the specifically
named local test DB is accepted; no fallback to the application DATABASE_URL.
Service commits release savepoints and all test data is rolled back.
"""
from datetime import timedelta
import os
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import httpx
import jwt
from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api import auth, local_auth, admin, enrollments, courses
from app.config import settings
from app.dependencies import get_db, require_instructor
from app.models.course import Course
from app.models.local_auth import LocalIdentity, LocalOTP, LocalSession
from app.models.user import User
from app.services import auth_service, local_auth_service as service
from app.utils.errors import register_exception_handlers


PASSWORD = "Local-password-123!"
LIVE = os.environ.get("LEARNCLOUD_RUN_AUTH_DB_TESTS") == "1"


def isolated_url(value):
    url = make_url(value)
    if (url.drivername not in {"postgresql", "postgresql+psycopg2"}
            or url.host not in {"127.0.0.1", "localhost", "::1"}
            or url.database != "learncloud_auth_test"
            or url.username != "learncloud_auth_test"
            or not set(url.query).issubset({"connect_timeout", "application_name"})):
        raise RuntimeError("Only the isolated local learncloud_auth_test database/user is permitted")
    return url


@pytest.fixture
def auth_db(db_session):
    if not LIVE:
        yield db_session
        return
    # Validation happens BEFORE constructing an engine; never use settings URL.
    engine = create_engine(isolated_url(os.environ["LEARNCLOUD_AUTH_TEST_DATABASE_URL"]), hide_parameters=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "learncloud_auth_test"
            assert connection.scalar(text("SELECT version FROM schema_migrations WHERE version='0007'")) == "0007"
            connection.rollback()
            outer = connection.begin()
            db = Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint")
            try:
                yield db
            finally:
                db.close()
                outer.rollback()
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def dual(auth_db, monkeypatch, rsa_key):
    for key, value in {
        "APP_ENV": "test", "LOCAL_AUTH_ENABLED": True,
        "LOCAL_AUTH_JWT_SECRET": SecretStr("test-only-local-auth-secret-" * 3),
        "COGNITO_REGION": "ap-southeast-1", "COGNITO_USER_POOL_ID": "ap-southeast-1_testpool",
        "COGNITO_APP_CLIENT_ID": "test-client", "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": 11025,
    }.items():
        monkeypatch.setattr(settings, key, value)
    # No AWS client may be constructed during these tests.
    monkeypatch.setattr("boto3.client", Mock(side_effect=AssertionError("AWS is forbidden")))
    monkeypatch.setattr(auth_service.jwt, "PyJWKClient", lambda *a, **kw: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=rsa_key.public_key())))
    messages = []
    if not LIVE:
        class SMTP:
            def __init__(self, host, port, timeout):
                assert (host, port) == ("127.0.0.1", 11025)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def send_message(self, message): messages.append(message)
        monkeypatch.setattr(service.smtplib, "SMTP", SMTP)

    app = FastAPI()
    register_exception_handlers(app)
    for router in (auth.router, local_auth.router, admin.router, enrollments.router, courses.router):
        app.include_router(router)
    app.dependency_overrides[get_db] = lambda: auth_db

    @app.get("/instructor-only")
    def protected(user=Depends(require_instructor)):
        return {"id": user.id}

    email = f"student-{uuid4().hex}@example.com"
    def code_for(recipient=email, purpose="verify"):
        subject = "Verify email" if purpose == "verify" else "Reset password"
        if LIVE:
            # Test-only Mailpit endpoint, no internet/AWS. Never echo body/code.
            rows = httpx.get("http://127.0.0.1:18025/api/v1/messages", timeout=5).json()["messages"]
            row = next(row for row in rows if subject in row["Subject"]
                       and any(to["Address"] == recipient for to in row["To"]))
            body = httpx.get(f"http://127.0.0.1:18025/api/v1/message/{row['ID']}", timeout=5).json()["Text"]
        else:
            body = next(m for m in reversed(messages) if m["To"] == recipient and subject in m["Subject"]).get_content()
        return re.search(r"\b(\d{6})\b", body).group(1)

    def cognito_token(sub, **changes):
        return jwt.encode({
            "sub": sub, "token_use": "access", "client_id": "test-client",
            "iss": "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_testpool",
            "exp": service.now() + timedelta(minutes=10), **changes,
        }, rsa_key, algorithm="RS256")

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, db=auth_db, email=email, messages=messages,
                              code=code_for, cognito_token=cognito_token)


def post(dual, action, **body):
    return dual.client.post("/auth/local/" + action, json={"email": dual.email, **body})


def signup(dual, verify=True):
    result = post(dual, "register", name="Student", password=PASSWORD)
    assert result.status_code == 201
    if verify:
        assert post(dual, "verify-email", code=dual.code()).status_code == 200
    return dual.db.query(User).filter_by(email=dual.email).one()


def login(dual):
    response = post(dual, "login", password=PASSWORD)
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_signup_password_email_and_verification(dual, caplog):
    user = signup(dual, verify=False)
    code = dual.code()
    assert user.role == "STUDENT" and user.cognito_sub is None
    assert user.password_hash.startswith("$argon2id$")
    assert service.password_hasher.verify(user.password_hash, PASSWORD)
    otp = dual.db.get(LocalOTP, (user.id, "verify"))
    assert len(otp.code_hash) == 64 and code not in otp.code_hash
    assert code not in caplog.text
    assert post(dual, "login", password=PASSWORD).status_code == 403
    result = post(dual, "verify-email", code=code)
    assert result.status_code == 200 and code not in result.text
    assert post(dual, "verify-email", code=code).status_code == 400
    assert dual.db.get(LocalIdentity, user.id).verified_at
    metadata = dual.db.get(LocalIdentity, user.id)
    assert metadata.provisioned_at is None and metadata.provisioned_by is None and metadata.provisioning_reference is None
    assert post(dual, "login", password=PASSWORD).status_code == 200


def test_resend_cooldown_invalidates_old_code(dual):
    user = signup(dual, verify=False)
    old_code = dual.code()
    assert post(dual, "resend-verification").status_code == 429
    otp = dual.db.get(LocalOTP, (user.id, "verify"))
    otp.sent_at = service.now() - timedelta(seconds=61)
    dual.db.commit()
    result = post(dual, "resend-verification")
    assert result.status_code == 200 and result.json()["retry_after"] == 60
    new_code = dual.code()
    assert new_code != old_code
    assert old_code not in result.text and new_code not in result.text
    assert post(dual, "verify-email", code=old_code).status_code == 400
    assert post(dual, "verify-email", code=new_code).status_code == 200


def test_expiry_and_attempt_limit(dual):
    user = signup(dual, verify=False)
    code = dual.code()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.LOCAL_AUTH_OTP_MAX_ATTEMPTS):
        assert post(dual, "verify-email", code=wrong).status_code == 400
    assert post(dual, "verify-email", code=code).status_code == 400
    otp = dual.db.get(LocalOTP, (user.id, "verify"))
    assert otp.attempts == settings.LOCAL_AUTH_OTP_MAX_ATTEMPTS
    otp.attempts, otp.expires_at = 0, service.now() - timedelta(seconds=1)
    dual.db.commit()
    assert post(dual, "verify-email", code=code).status_code == 400


def test_logout_revokes_only_that_session(dual):
    user = signup(dual)
    first, second = login(dual), login(dual)
    assert dual.client.get("/auth/me", headers=headers(first)).status_code == 200
    assert dual.client.post("/auth/local/logout", headers=headers(first)).status_code == 200
    assert dual.client.get("/auth/me", headers=headers(first)).status_code == 401
    assert dual.client.get("/auth/me", headers=headers(second)).status_code == 200
    assert dual.db.query(LocalSession).filter(LocalSession.user_id == user.id,
                                              LocalSession.revoked_at.is_not(None)).count() == 1


@pytest.mark.parametrize("changes", [
    {"exp": 0}, {"iss": "wrong"}, {"aud": "wrong"}, {"token_use": "id"},
    {"auth_provider": "cognito"}, {"jti": "not-a-session"}, {"sub": "999999"}, {"iat": 9999999999},
])
def test_local_claims_are_validated(dual, changes):
    signup(dual)
    claims = jwt.decode(login(dual), settings.LOCAL_AUTH_JWT_SECRET.get_secret_value(),
                        algorithms=["HS256"], audience=settings.LOCAL_AUTH_JWT_AUDIENCE)
    token = jwt.encode({**claims, **changes}, settings.LOCAL_AUTH_JWT_SECRET.get_secret_value(), algorithm="HS256")
    assert dual.client.get("/auth/me", headers=headers(token)).status_code == 401


def test_tampered_unsigned_and_missing_claim_tokens_fail(dual):
    signup(dual)
    token = login(dual)
    claims = jwt.decode(token, options={"verify_signature": False})
    bad = [jwt.encode(claims, "different-signing-secret-" * 3, algorithm="HS256"),
           jwt.encode(claims, "", algorithm="none"), "mock:1:1", "invalid"]
    for claim in ("exp", "iat", "iss", "aud", "sub", "jti"):
        bad.append(jwt.encode({k:v for k,v in claims.items() if k != claim},
                              settings.LOCAL_AUTH_JWT_SECRET.get_secret_value(), algorithm="HS256"))
    for candidate in bad:
        assert dual.client.get("/auth/me", headers=headers(candidate)).status_code == 401
    assert dual.client.get("/auth/me", headers={"X-Demo-User": "1"}).status_code == 401


def test_role_is_current_database_value_not_token_or_client(dual):
    user = signup(dual)
    assert post(dual, "register", name="X", password=PASSWORD, role="ADMIN").status_code == 422
    token = login(dual)
    assert dual.client.patch("/auth/me", json={"role": "ADMIN"}, headers=headers(token)).status_code == 422
    dual.db.execute(update(User).where(User.id == user.id).values(role="INSTRUCTOR"))
    dual.db.commit()
    assert dual.client.get("/instructor-only", headers=headers(token)).status_code == 200
    dual.db.expire_on_commit = False
    cached = dual.db.get(User, user.id)
    dual.db.execute(update(User).where(User.id == user.id).values(role="STUDENT"),
                    execution_options={"synchronize_session": False})
    dual.db.commit()
    assert cached.role == "INSTRUCTOR"
    claims = jwt.decode(token, options={"verify_signature": False})
    forged_role = jwt.encode({**claims, "role": "ADMIN", "cognito:groups": ["ADMIN"]},
                             settings.LOCAL_AUTH_JWT_SECRET.get_secret_value(), algorithm="HS256")
    assert dual.client.get("/instructor-only", headers=headers(forged_role)).status_code == 403
    assert dual.client.get("/auth/me", headers=headers(token)).json()["role"] == "STUDENT"
    assert dual.client.get("/admin/users", headers=headers(token)).status_code == 403


def test_reset_and_change_password_revoke_sessions(dual):
    signup(dual)
    token = login(dual)
    assert post(dual, "forgot-password").status_code == 200
    reset_code = dual.code(purpose="reset")
    assert post(dual, "verify-email", code=reset_code).status_code == 400
    assert post(dual, "reset-password", code=reset_code, password="New-password-123!").status_code == 200
    assert dual.client.get("/auth/me", headers=headers(token)).status_code == 401
    assert post(dual, "login", password=PASSWORD).status_code == 401
    result = post(dual, "login", password="New-password-123!")
    token = result.json()["access_token"]
    result = dual.client.post("/auth/local/change-password", headers=headers(token),
                              json={"current_password": "New-password-123!", "new_password": PASSWORD})
    assert result.status_code == 200
    assert dual.client.get("/auth/me", headers=headers(token)).status_code == 401
    assert post(dual, "reset-password", code=reset_code, password="Another-password!").status_code == 400
    assert post(dual, "login", password=PASSWORD).status_code == 200


def test_recovery_is_neutral_for_unknown_and_cognito_email(dual):
    unknown = post(dual, "forgot-password").json()
    user = User(name="Cognito", email=dual.email, role="ADMIN", cognito_sub="cognito-admin")
    dual.db.add(user)
    dual.db.commit()
    assert post(dual, "forgot-password").json() == unknown
    assert post(dual, "resend-verification").json() == unknown
    assert post(dual, "login", password=PASSWORD).status_code == 401
    assert post(dual, "register", name="X", password=PASSWORD).status_code == 409
    assert dual.db.get(LocalIdentity, user.id) is None


def test_cognito_cannot_take_local_or_unlinked_identity(dual):
    user = signup(dual)
    encoded = user.password_hash
    attacker = dual.cognito_token("attacker", email=user.email, **{"cognito:groups": ["ADMIN"]})
    assert dual.client.get("/auth/me", headers=headers(attacker)).status_code == 401
    claims = jwt.decode(attacker, options={"verify_signature": False})
    with pytest.raises(auth_service.InvalidToken):
        auth_service.sync_authorizer_claims(dual.db, claims)
    dual.db.refresh(user)
    assert user.cognito_sub is None and user.password_hash == encoded and user.role == "STUDENT"
    assert post(dual, "login", password=PASSWORD).status_code == 200
    # Pre-existing, unlinked privileged users also cannot be linked by email.
    legacy = User(name="Legacy", email=f"legacy-{uuid4().hex}@example.com", role="ADMIN")
    dual.db.add(legacy)
    dual.db.commit()
    assert dual.client.get("/auth/me", headers=headers(dual.cognito_token("new", email=legacy.email))).status_code == 401


def test_both_providers_use_same_database_and_separate_accounts(dual):
    local_user = signup(dual)
    local_token = login(dual)
    cognito = User(name="Cognito", email=f"cognito-{uuid4().hex}@example.com", role="STUDENT", cognito_sub=uuid4().hex)
    instructor = User(name="Instructor", email=f"instructor-{uuid4().hex}@example.com", role="INSTRUCTOR", cognito_sub=uuid4().hex)
    dual.db.add_all([cognito, instructor])
    dual.db.flush()
    course = Course(instructor_id=instructor.id, title="Shared database course", status="PUBLISHED")
    dual.db.add(course)
    dual.db.commit()
    cognito_token = dual.cognito_token(cognito.cognito_sub, **{"cognito:groups": ["ADMIN"]})
    assert dual.client.get("/auth/me", headers=headers(cognito_token)).json()["role"] == "STUDENT"
    for token in (local_token, cognito_token):
        assert dual.client.post(f"/courses/{course.id}/enroll", headers=headers(token)).status_code == 201
        result = dual.client.get("/students/me/courses", headers=headers(token))
        assert result.status_code == 200 and result.json()[0]["course"]["id"] == course.id
    assert dual.client.get("/auth/me", headers=headers(local_token)).json()["id"] == local_user.id
    assert dual.client.get("/auth/me", headers=headers(cognito_token)).json()["id"] == cognito.id
    # Changing provider never rebinds or copies the role/session to the other.
    assert dual.client.post("/auth/local/logout", headers=headers(cognito_token)).status_code == 401
    assert dual.client.get("/auth/me", headers=headers(cognito_token)).status_code == 200


@pytest.mark.parametrize("environment,enabled", [("production", True), ("staging", True), ("development", False), ("test", False)])
def test_backend_gate_blocks_local_only(dual, monkeypatch, environment, enabled):
    signup(dual)
    token = login(dual)
    monkeypatch.setattr(settings, "APP_ENV", environment)
    monkeypatch.setattr(settings, "LOCAL_AUTH_ENABLED", enabled)
    assert post(dual, "login", password=PASSWORD).status_code == 503
    assert dual.client.get("/auth/me", headers=headers(token)).status_code == 401
    cognito = User(name="Cognito", email=f"cognito-{uuid4().hex}@example.com", role="STUDENT", cognito_sub=uuid4().hex)
    dual.db.add(cognito)
    dual.db.commit()
    assert dual.client.get("/auth/me", headers=headers(dual.cognito_token(cognito.cognito_sub))).status_code == 200


def test_login_attempts_are_limited(dual):
    signup(dual)
    for _ in range(settings.LOCAL_AUTH_LOGIN_MAX_ATTEMPTS):
        assert post(dual, "login", password="wrong-password").status_code == 401
    assert post(dual, "login", password=PASSWORD).status_code == 429


def test_smtp_failure_does_not_leave_half_registered_account(dual, monkeypatch):
    monkeypatch.setattr(service.smtplib, "SMTP", Mock(side_effect=OSError("sensitive SMTP details")))
    result = post(dual, "register", name="Student", password=PASSWORD)
    assert result.status_code == 503 and "sensitive" not in result.text
    assert dual.db.query(User).filter_by(email=dual.email).first() is None


def test_weak_or_missing_local_secret_blocks_service(dual, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_AUTH_JWT_SECRET", SecretStr("weak"))
    assert post(dual, "register", name="Student", password=PASSWORD).status_code == 503


def test_legacy_password_hash_is_not_automatically_enrolled(dual):
    user = User(name="Legacy", email=dual.email, role="ADMIN", cognito_sub=None,
                password_hash=service.password_hasher.hash(PASSWORD))
    dual.db.add(user)
    dual.db.commit()
    assert post(dual, "login", password=PASSWORD).status_code == 401
    assert post(dual, "register", name="Student", password=PASSWORD).status_code == 409
    assert dual.db.get(LocalIdentity, user.id) is None


def test_failed_resend_preserves_previous_code(dual, monkeypatch):
    user = signup(dual, verify=False)
    old_code = dual.code()
    otp = dual.db.get(LocalOTP, (user.id, "verify"))
    old_hash = otp.code_hash
    otp.sent_at = service.now() - timedelta(seconds=61)
    dual.db.commit()
    monkeypatch.setattr(service.smtplib, "SMTP", Mock(side_effect=OSError("unavailable")))
    assert post(dual, "resend-verification").status_code == 503
    dual.db.refresh(otp)
    assert otp.code_hash == old_hash
    assert post(dual, "verify-email", code=old_code).status_code == 200


def test_database_session_expiry_is_checked(dual):
    user = signup(dual)
    token = login(dual)
    session = dual.db.query(LocalSession).filter_by(user_id=user.id).one()
    session.expires_at = service.now() - timedelta(seconds=1)
    dual.db.commit()
    assert dual.client.get("/auth/me", headers=headers(token)).status_code == 401


def test_admin_manages_local_role_without_calling_cognito(dual):
    user = signup(dual)
    token = login(dual)
    administrator = User(name="Admin", email=f"admin-{uuid4().hex}@example.com", role="ADMIN", cognito_sub=uuid4().hex)
    dual.db.add(administrator)
    dual.db.commit()
    admin_headers = headers(dual.cognito_token(administrator.cognito_sub))
    result = dual.client.patch(f"/admin/users/{user.id}", headers=admin_headers, json={"role": "INSTRUCTOR", "name": "Updated"})
    assert result.status_code == 200
    assert dual.client.get("/instructor-only", headers=headers(token)).status_code == 200
    assert dual.client.patch(f"/admin/users/{user.id}", headers=admin_headers, json={"role": "STUDENT"}).status_code == 200
    assert dual.client.get("/instructor-only", headers=headers(token)).status_code == 403
    assert dual.client.patch(f"/admin/users/{user.id}", headers=admin_headers,
                             json={"email": "unverified-new@example.com"}).status_code == 409


def test_cognito_confirmation_cannot_overwrite_local_user(dual, monkeypatch):
    user = signup(dual)
    encoded = user.password_hash
    # Only these Cognito responses are simulated, never a real AWS operation.
    client = Mock()
    client.admin_get_user.return_value = {"Enabled": True, "UserStatus": "CONFIRMED", "UserAttributes": [
        {"Name": "sub", "Value": "attacker"}, {"Name": "email", "Value": dual.email},
        {"Name": "email_verified", "Value": "true"}]}
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)
    result = dual.client.post("/auth/verify-email", json={"email": dual.email, "code": "123456"})
    assert result.status_code == 409
    dual.db.refresh(user)
    assert user.cognito_sub is None and user.password_hash == encoded
    assert dual.client.post("/auth/register", json={"email": dual.email, "password": PASSWORD, "name": "Other"}).status_code == 409
    client.sign_up.assert_not_called()


def test_auth_validation_never_echoes_password_or_otp(dual):
    result = post(dual, "verify-email", code="7654321")
    assert result.status_code == 422 and "7654321" not in result.text
    result = post(dual, "register", name="Student", password="short42")
    assert result.status_code == 422 and "short42" not in result.text


@pytest.mark.parametrize("value", [
    "postgresql://user@production.example.com/learncloud",
    "postgresql://user@127.0.0.1/learncloud",  # Also refuse a local RDS tunnel.
    "postgresql://learncloud_auth_test@127.0.0.1/learncloud_auth_test?host=production.example.com",
])
def test_test_database_guard_refuses_other_targets(value):
    with pytest.raises(RuntimeError): isolated_url(value)


def test_database_and_migration_contract():
    root = Path(__file__).resolve().parents[3]
    database = (root / "backend/app/database.py").read_text(encoding="utf-8-sig")
    assert "database_url = settings.DATABASE_URL" in database
    assert "boto3" not in database and "DB_HOST" not in database
    sql = (root / "database/migrations/0007_dual_auth.sql").read_text()
    assert sql.startswith("BEGIN;") and sql.rstrip().endswith("COMMIT;")
    assert "UPDATE users" not in sql and "DELETE" not in sql.replace("ON DELETE CASCADE", "")
