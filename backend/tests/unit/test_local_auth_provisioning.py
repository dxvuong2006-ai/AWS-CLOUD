"""Runtime/guards offline, plus genuine operator SQL authorization on opt-in PG.

Shares the strict isolated local database guard with test_dual_auth. No RDS URL
or application DATABASE_URL fallback, no AWS operations, no live email recovery.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text, update
from sqlalchemy.orm import Session

from test_dual_auth import (dual, auth_db, rsa_key, headers, isolated_url, LIVE, PASSWORD)
from app.models.course import Course
from app.models.section import Section
from app.models.lesson import Lesson
from app.models.local_auth import LocalIdentity, LocalOTP
from app.models.user import User
from app.models.video_pipeline import VideoUpload, VideoPipelineRun
from app.services import auth_service, local_auth_service as auth, local_auth_provisioning as provisioning


def account(dual, role="INSTRUCTOR", linked=True):
    user = User(name="Existing account", email=f"existing-{uuid4().hex}@example.com", role=role,
                cognito_sub=uuid4().hex if linked else None)
    dual.db.add(user)
    dual.db.commit()
    return user


def approved_fixture(dual, user):
    # A database fixture representing an operator-approved enrollment. Separate
    # PG tests below exercise the provisioning function and real authorization.
    user.password_hash = auth.password_hasher.hash(PASSWORD)
    dual.db.add(LocalIdentity(user_id=user.id, verified_at=auth.now(), provisioned_at=auth.now(),
                             provisioned_by="test_authorized_dba", provisioning_reference="TEST-APPROVAL-1"))
    dual.db.commit()


def sign_in(dual, user, password=PASSWORD):
    response = dual.client.post("/auth/local/login", json={"email": user.email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def stable_identity(user):
    return (user.id, user.name, user.email, user.role, user.cognito_sub, user.created_at)


def business_snapshot(db):
    return {model.__tablename__: [tuple(getattr(row, c.name) for c in model.__table__.columns)
             for row in db.query(model).order_by(model.id).all()]
            for model in (Course, Section, Lesson, VideoUpload, VideoPipelineRun)}


def owned_content(dual, user):
    course = Course(instructor_id=user.id, title="Existing course", status="DRAFT")
    dual.db.add(course); dual.db.flush()
    section = Section(course_id=course.id, title="Existing section", position=1)
    dual.db.add(section); dual.db.flush()
    lesson = Lesson(section_id=section.id, title="Existing lesson", position=1,
                    raw_video_key="unchanged/source.mp4", processed_video_key="unchanged/video.mp4")
    dual.db.add(lesson); dual.db.flush()
    upload = VideoUpload(id=uuid4().hex, lesson_id=lesson.id, source_key=f"existing/{uuid4().hex}.mp4",
                         content_type="video/mp4", size_bytes=100, expires_at=auth.now()+timedelta(hours=1))
    dual.db.add(upload); dual.db.flush()
    dual.db.add(VideoPipelineRun(id=uuid4().hex, upload_id=upload.id, lesson_id=lesson.id, attempt=0,
        state="COMPLETE", source_etag="unchanged-etag", output_key="unchanged/video.mp4"))
    dual.db.commit()
    return course


@pytest.mark.parametrize("role", ["INSTRUCTOR", "ADMIN"])
@pytest.mark.parametrize("linked", [True, False])
def test_local_login_uses_same_privileged_user_and_keeps_cognito(dual, role, linked):
    user = account(dual, role, linked)
    before, count = stable_identity(user), dual.db.query(User).count()
    approved_fixture(dual, user)
    token = sign_in(dual, user)
    me = dual.client.get("/auth/me", headers=headers(token))
    assert me.status_code == 200
    assert me.json()["id"] == user.id and me.json()["role"] == role
    assert dual.client.get("/admin/users", headers=headers(token)).status_code == (200 if role == "ADMIN" else 403)
    assert dual.client.get("/instructor-only", headers=headers(token)).status_code == (200 if role == "INSTRUCTOR" else 403)
    encoded = user.password_hash
    if linked:
        cognito = dual.cognito_token(user.cognito_sub, email=user.email, name=user.name)
        assert dual.client.get("/auth/me", headers=headers(cognito)).json()["id"] == user.id
        dual.db.refresh(user)
        assert user.password_hash == encoded
        assert dual.client.get("/auth/me", headers=headers(token)).status_code == 200
        sign_in(dual, user)
    assert stable_identity(user) == before and dual.db.query(User).count() == count


def test_course_section_lesson_video_relationships_survive_both_logins(dual):
    user = account(dual)
    course = owned_content(dual, user)
    before = business_snapshot(dual.db)
    approved_fixture(dual, user)
    for token in (sign_in(dual, user), dual.cognito_token(user.cognito_sub)):
        response = dual.client.get("/courses/instructor/me", headers=headers(token))
        assert response.status_code == 200
        found = next(row for row in response.json() if row["id"] == course.id)
        assert found["instructor_id"] == user.id
        assert found["sections"][0]["lessons"][0]["title"] == "Existing lesson"
        dual.db.expire_all()
        assert business_snapshot(dual.db) == before


@pytest.mark.parametrize("demote", [False, True])
@pytest.mark.parametrize("linked", [False, True])
def test_mailpit_codes_cannot_take_provisioned_account_even_after_demotion(dual, monkeypatch, demote, linked):
    user = account(dual, linked=linked)
    approved_fixture(dual, user)
    if demote:
        user.role = "STUDENT"
    encoded = user.password_hash
    # Even possession of a genuine, still-valid database OTP is insufficient.
    for purpose in ("verify", "reset"):
        nonce = uuid4().hex
        dual.db.add(LocalOTP(user_id=user.id, purpose=purpose, nonce=nonce,
            code_hash=auth._otp_hash(user.id, purpose, nonce, "654321"), sent_at=auth.now(),
            expires_at=auth.now()+timedelta(minutes=5), attempts=0))
    dual.db.commit()
    smtp = Mock(side_effect=AssertionError("Privileged recovery must never reach Mailpit"))
    monkeypatch.setattr(auth.smtplib, "SMTP", smtp)
    unknown = dual.client.post("/auth/local/forgot-password", json={"email": "unknown@example.com"}).json()
    for action in ("forgot-password", "resend-verification"):
        assert dual.client.post("/auth/local/"+action, json={"email": user.email}).json() == unknown
    assert dual.client.post("/auth/local/verify-email", json={"email": user.email, "code": "654321"}).status_code == 400
    assert dual.client.post("/auth/local/reset-password", json={"email": user.email, "code": "654321", "password": "attacker-password123"}).status_code == 400
    smtp.assert_not_called()
    dual.db.refresh(user)
    assert user.password_hash == encoded
    sign_in(dual, user)


def test_privileged_local_password_changed_only_with_current_password(dual):
    user = account(dual, "ADMIN")
    approved_fixture(dual, user)
    token = sign_in(dual, user)
    request = {"current_password": "wrong-password", "new_password": "New-instructor-123!"}
    assert dual.client.post("/auth/local/change-password", json=request, headers=headers(token)).status_code == 400
    request["current_password"] = PASSWORD
    assert dual.client.post("/auth/local/change-password", json=request, headers=headers(token)).status_code == 200
    assert dual.client.get("/auth/me", headers=headers(token)).status_code == 401
    sign_in(dual, user, request["new_password"])
    assert dual.client.get("/auth/me", headers=headers(dual.cognito_token(user.cognito_sub))).status_code == 200
    sign_in(dual, user, request["new_password"])


def test_cognito_confirmation_preserves_local_password(dual, monkeypatch):
    user = account(dual)
    approved_fixture(dual, user)
    encoded = user.password_hash
    client = Mock()
    client.admin_get_user.return_value = {"Enabled": True, "UserStatus": "CONFIRMED", "UserAttributes": [
        {"Name": "sub", "Value": user.cognito_sub}, {"Name": "email", "Value": user.email},
        {"Name": "email_verified", "Value": "true"},
        {"Name": "name", "Value": user.name}]}
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)
    assert dual.client.post("/auth/verify-email", json={"email": user.email, "code": "123456"}).status_code == 200
    dual.db.refresh(user)
    assert user.password_hash == encoded
    sign_in(dual, user)


def test_unprovisioned_linked_identity_stays_ineligible_and_public_cannot_provision(dual):
    user = account(dual)
    user.password_hash = auth.password_hasher.hash(PASSWORD)
    dual.db.add(LocalIdentity(user_id=user.id, verified_at=auth.now()))
    dual.db.commit()
    assert dual.client.post("/auth/local/login", json={"email": user.email,"password": PASSWORD}).status_code == 401
    assert dual.client.post("/auth/local/register", json={"name": "Attacker", "email": user.email, "password": PASSWORD}).status_code == 409
    assert dual.client.post("/auth/local/register", json={"name": "Attacker", "email": user.email, "password": PASSWORD,
        "user_id": user.id, "provisioned_at": "now", "role": "ADMIN"}).status_code == 422
    token = dual.cognito_token(user.cognito_sub)
    assert dual.client.post("/auth/local/provision", json={"user_id": user.id}, headers=headers(token)).status_code == 404
    assert dual.client.patch("/auth/me", json={"provisioned_at": "now"}, headers=headers(token)).status_code == 422


def test_same_local_and_cognito_tokens_observe_role_revocation(dual):
    user = account(dual, "ADMIN")
    approved_fixture(dual, user)
    tokens = (sign_in(dual, user), dual.cognito_token(user.cognito_sub, **{"cognito:groups": ["ADMIN"]}))
    for token in tokens:
        assert dual.client.get("/admin/users", headers=headers(token)).status_code == 200
    dual.db.execute(update(User).where(User.id == user.id).values(role="STUDENT"))
    dual.db.commit()
    for token in tokens:
        assert dual.client.get("/admin/users", headers=headers(token)).status_code == 403
        assert dual.client.get("/auth/me", headers=headers(token)).json()["role"] == "STUDENT"


def test_provisioning_refuses_non_postgresql_operator_authorization(dual):
    if LIVE:
        pytest.skip("SQLite fail-closed check is covered by offline run")
    with pytest.raises(provisioning.ProvisioningError, match="PostgreSQL"):
        provisioning.require_operator(dual.db)


def target(user):
    return {"user_id": user.id, "expected_email": user.email, "expected_role": user.role,
            "expected_cognito_sub": user.cognito_sub}


@pytest.mark.skipif(not LIVE, reason="Real PostgreSQL operator membership, no mocked authorization")
@pytest.mark.parametrize("role", ["INSTRUCTOR", "ADMIN"])
@pytest.mark.parametrize("linked", [True, False])
def test_postgres_provisioning_preview_write_boundaries_and_existing_data(dual, role, linked):
    user = account(dual, role, linked)
    owner = user if role == "INSTRUCTOR" else account(dual)
    owned_content(dual, owner)
    before, identity, count = business_snapshot(dual.db), stable_identity(user), dual.db.query(User).count()
    # The original authenticated test-cluster superuser impersonates the
    # separately granted login to exercise its real, narrow PostgreSQL ACLs.
    dual.db.execute(text("SET SESSION AUTHORIZATION learncloud_auth_operator"))
    statements = []
    connection = dual.db.connection()
    capture = lambda conn, cursor, statement, params, context, many: statements.append(statement.lower())
    event.listen(connection, "before_cursor_execute", capture)
    try:
        inspected, operator = provisioning.inspect_target(dual.db, **target(user))
        assert inspected.id == user.id and operator == "learncloud_auth_operator"
        assert not any(s.lstrip().startswith(("insert ", "update ", "delete ", "create ", "alter ")) for s in statements)
        statements.clear()
        result = provisioning.provision(dual.db, **target(user), password=PASSWORD, approval_reference="TEST-APPROVAL-2")
        dual.db.commit()
    finally:
        event.remove(connection, "before_cursor_execute", capture)
        dual.db.execute(text("RESET SESSION AUTHORIZATION"))
    writes = [s for s in statements if s.lstrip().startswith(("insert ", "update ", "delete "))]
    assert len(writes) == 2
    assert any(s.startswith("update users set password_hash=") for s in writes)
    assert any(s.startswith("insert into local_auth_identities") for s in writes)
    dual.db.expire_all()
    assert business_snapshot(dual.db) == before and stable_identity(user) == identity
    assert dual.db.query(User).count() == count
    metadata = dual.db.get(LocalIdentity, user.id)
    assert metadata.provisioned_by == result["provisioned_by"] == operator
    assert metadata.provisioning_reference == "TEST-APPROVAL-2"
    assert user.password_hash.startswith("$argon2id$")
    sign_in(dual, user)
    with pytest.raises(provisioning.ProvisioningError, match="already exists"):
        provisioning.provision(dual.db, **target(user), password="replacement-password!", approval_reference="TEST-3")


@pytest.mark.skipif(not LIVE, reason="Real PostgreSQL authorization and locked target checks")
@pytest.mark.parametrize("change", ["id", "email", "role", "subject", "student", "password", "reference", "existing_hash", "ambiguous_email"])
def test_postgres_wrong_target_or_unsafe_input_never_enrolls(dual, change):
    user = account(dual)
    kwargs = {**target(user), "password": PASSWORD, "approval_reference": "TEST-APPROVAL-3"}
    if change == "id": kwargs["user_id"] = 2147483647
    if change == "email": kwargs["expected_email"] = "different@example.com"
    if change == "role": kwargs["expected_role"] = "ADMIN"
    if change == "subject": kwargs["expected_cognito_sub"] = "different-subject"
    if change == "student": user.role = "STUDENT"; kwargs["expected_role"] = "STUDENT"
    if change == "password": kwargs["password"] = "short"
    if change == "reference": kwargs["approval_reference"] = "bad reference\n"
    if change == "existing_hash": user.password_hash = auth.password_hasher.hash("existing-password!")
    if change == "ambiguous_email":
        dual.db.add(User(name="Different user", email=user.email.upper(), role="STUDENT", cognito_sub=uuid4().hex))
    dual.db.commit()
    with pytest.raises(provisioning.ProvisioningError):
        provisioning.provision(dual.db, **kwargs)
    assert dual.db.get(LocalIdentity, user.id) is None


@pytest.mark.skipif(not LIVE, reason="Genuine unauthenticated-role PostgreSQL connection")
def test_postgres_unapproved_login_and_set_role_are_rejected(dual):
    import os
    url = isolated_url(os.environ["LEARNCLOUD_AUTH_TEST_DATABASE_URL"]).set(username="learncloud_auth_denied")
    engine = create_engine(url, hide_parameters=True)
    try:
        with Session(engine) as denied:
            with pytest.raises(provisioning.ProvisioningError, match="DBA-authorized"):
                provisioning.require_operator(denied)
    finally:
        engine.dispose()
    dual.db.execute(text("SET LOCAL ROLE learncloud_auth_denied"))
    try:
        with pytest.raises(provisioning.ProvisioningError): provisioning.require_operator(dual.db)
    finally:
        dual.db.execute(text("RESET ROLE"))


def test_cli_refuses_piped_passwords_before_any_connection(monkeypatch):
    from scripts import provision_local_auth as cli
    engine = Mock(side_effect=AssertionError("No DB connection is allowed"))
    monkeypatch.setattr("sqlalchemy.create_engine", engine)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit, match="interactive"):
        cli.main(["--user-id", "1", "--expected-email", "target@example.com", "--expected-role", "ADMIN",
                  "--expected-cognito-sub", "NONE", "--operator-db-user", "operator", "--approval-reference", "TEST-4", "--apply"])
    engine.assert_not_called()


@pytest.mark.skipif(not LIVE, reason="Runs the actual CLI against isolated PostgreSQL with narrow operator ACLs")
def test_actual_cli_preview_confirmation_and_apply(dual, monkeypatch, capsys):
    import os
    from scripts import provision_local_auth as cli
    from app.config import settings
    url = isolated_url(os.environ["LEARNCLOUD_AUTH_TEST_DATABASE_URL"])
    engine = create_engine(url, hide_parameters=True)
    # Separate committed fixture so the CLI's own connection can see it.
    email, sub = f"cli-{uuid4().hex}@example.com", uuid4().hex
    with engine.begin() as c:
        uid = c.execute(text("INSERT INTO users(name,email,role,cognito_sub) VALUES ('CLI Instructor',:email,'INSTRUCTOR',:sub) RETURNING id"),
                        {"email": email, "sub": sub}).scalar_one()
    try:
        monkeypatch.setattr(settings, "DATABASE_URL", url.render_as_string(hide_password=False))
        monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
        args = ["--user-id", str(uid), "--expected-email", email, "--expected-role", "INSTRUCTOR",
                "--expected-cognito-sub", sub, "--operator-db-user", "learncloud_auth_operator", "--approval-reference", "TEST-CLI-5"]
        monkeypatch.setattr(cli.getpass, "getpass", lambda *args: "")  # Isolated cluster uses loopback trust.
        assert cli.main(args) == 0
        with engine.connect() as c:
            assert c.scalar(text("SELECT password_hash FROM users WHERE id=:id"), {"id":uid}) is None
            assert c.scalar(text("SELECT count(*) FROM local_auth_identities WHERE user_id=:id"), {"id":uid}) == 0
        monkeypatch.setattr("builtins.input", lambda *args: "WRONG CONFIRMATION")
        assert cli.main(args+["--apply"]) == 1
        with engine.connect() as c:
            assert c.scalar(text("SELECT password_hash FROM users WHERE id=:id"), {"id":uid}) is None
        answers = iter(["", PASSWORD, PASSWORD])
        monkeypatch.setattr(cli.getpass, "getpass", lambda *args: next(answers))
        monkeypatch.setattr("builtins.input", lambda *args: f"PROVISION {uid}")
        assert cli.main(args+["--apply"]) == 0
        with engine.connect() as c:
            row = c.execute(text("SELECT u.id,u.email,u.role,u.cognito_sub,u.password_hash,i.provisioned_by FROM users u JOIN local_auth_identities i ON i.user_id=u.id WHERE u.id=:id"), {"id":uid}).mappings().one()
            assert (row["id"],row["email"],row["role"],row["cognito_sub"]) == (uid,email,"INSTRUCTOR",sub)
            assert auth.password_hasher.verify(row["password_hash"], PASSWORD)
            assert row["provisioned_by"] == "learncloud_auth_operator"
        monkeypatch.setattr(cli.getpass, "getpass", lambda *args: "")
        assert cli.main(args+["--apply"]) == 1  # One-time only; does not replace credentials.
        output = capsys.readouterr()
        assert PASSWORD not in output.out + output.err and "$argon2" not in output.out + output.err
    finally:
        # Only the committed fixture in the previously validated isolated DB.
        with engine.begin() as c:
            c.execute(text("DELETE FROM users WHERE id=:id"), {"id":uid})
        engine.dispose()
