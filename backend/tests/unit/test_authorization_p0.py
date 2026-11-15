"""Authorization regressions using SQLite and real local RSA-signed JWTs.

Only JWKS retrieval and Cognito administrative side effects are mocked.
Identity, JWT decoding, role checks, ownership and persistence use real code.
"""

import time
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, select, update
from sqlalchemy.dialects import postgresql

from app.api import admin, auth, flashcards
from app.config import settings
from app.dependencies import get_db
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.flashcard import Flashcard
from app.models.lesson import Lesson
from app.models.section import Section
from app.models.user import User
from app.services import auth_service
from app.utils.errors import register_exception_handlers


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def security(db_session, monkeypatch, signing_key):
    monkeypatch.setattr(settings, "COGNITO_REGION", "ap-southeast-1")
    monkeypatch.setattr(settings, "COGNITO_USER_POOL_ID", "ap-southeast-1_testpool")
    monkeypatch.setattr(settings, "COGNITO_APP_CLIENT_ID", "test-client")
    db = db_session
    for uid, role in ((1, "INSTRUCTOR"), (2, "STUDENT"), (3, "INSTRUCTOR"), (4, "ADMIN")):
        db.add(User(id=uid, cognito_sub=f"sub-{uid}", name=f"User {uid}",
                    email=f"user{uid}@example.com", role=role))
    db.commit()
    for cid, owner in ((1, 1), (2, 3)):
        db.add(Course(id=cid, instructor_id=owner, title=f"Course {cid}"))
    db.commit()
    for sid in (1, 2):
        db.add(Section(id=sid, course_id=sid, title="Section", position=1))
    db.commit()
    for lid in (1, 2):
        db.add(Lesson(id=lid, section_id=lid, title="Lesson", position=1))
    db.commit()
    for cid in (1, 2):
        db.add(Flashcard(id=cid, lesson_id=cid, front="Original", back="Answer",
                         position=1, is_approved=False))
    db.commit()

    jwks = SimpleNamespace(get_signing_key_from_jwt=lambda token:
                           SimpleNamespace(key=signing_key.public_key()))
    monkeypatch.setattr(auth_service.jwt, "PyJWKClient", lambda *a, **kw: jwks)
    profile = Mock()
    role_sync = Mock()
    monkeypatch.setattr(auth_service, "admin_update_profile", profile)
    monkeypatch.setattr(auth_service, "admin_update_role", role_sync)
    monkeypatch.setattr(auth_service, "cognito_client",
                        Mock(side_effect=AssertionError("Live Cognito is forbidden")))

    def claims(uid, groups=None):
        result = {
            "sub": f"sub-{uid}", "token_use": "access", "client_id": "test-client",
            "iss": "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_testpool",
            "exp": int(time.time()) + 600,
        }
        if groups is not None:
            result["cognito:groups"] = groups
        return result

    def token(uid, groups=None, **changes):
        return jwt.encode({**claims(uid, groups), **changes}, signing_key, algorithm="RS256")

    def headers(uid, groups=None):
        return {"Authorization": f"Bearer {token(uid, groups)}"}

    app = FastAPI()
    for router in (auth.router, admin.router, flashcards.router):
        app.include_router(router)
    register_exception_handlers(app)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(db=db, client=client, app=app, claims=claims,
                              token=token, headers=headers, profile=profile,
                              role_sync=role_sync)


@pytest.mark.parametrize("group", [["INSTRUCTOR"], ["ADMIN"], '["ADMIN"]'])
def test_old_privileged_groups_cannot_restore_demoted_role(security, group):
    response = security.client.get("/auth/me", headers=security.headers(2, group))
    assert response.status_code == 200
    assert response.json()["role"] == "STUDENT"
    assert security.db.get(User, 2).role == "STUDENT"
    denied = security.client.get("/admin/users", headers=security.headers(2, group))
    assert denied.status_code == 403


@pytest.mark.parametrize("groups", [[], ["STUDENT"]])
def test_database_admin_does_not_lose_role_to_token_groups(security, groups):
    response = security.client.get("/admin/users", headers=security.headers(4, groups))
    assert response.status_code == 200
    assert security.db.get(User, 4).role == "ADMIN"


def test_authorizer_claims_use_same_database_role_policy(security):
    user = auth_service.sync_authorizer_claims(security.db, security.claims(2, ["ADMIN"]))
    assert user.role == "STUDENT"
    assert security.db.get(User, 2).role == "STUDENT"


def test_cached_identity_observes_committed_database_role_change(security):
    security.db.expire_on_commit = False
    cached = security.db.get(User, 1)
    security.db.execute(update(User).where(User.id == 1).values(role="STUDENT"),
                        execution_options={"synchronize_session": False})
    security.db.commit()
    assert cached.role == "INSTRUCTOR"  # Identity-map cache is deliberately stale.
    response = security.client.get("/auth/me", headers=security.headers(1))
    assert response.status_code == 200
    assert response.json()["role"] == "STUDENT"


def test_unprovisioned_identity_cannot_bootstrap_admin_from_groups(security, monkeypatch):
    client = Mock()
    client.admin_get_user.return_value = {
        "Enabled": True,
        "UserStatus": "CONFIRMED",
        "UserAttributes": [
            {"Name": "sub", "Value": "sub-99"},
            {"Name": "email", "Value": "new@example.com"},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": "New user"},
        ],
    }
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)
    claims = {**security.claims(99, ["ADMIN"]), "username": "new-user"}
    user = auth_service.sync_authorizer_claims(security.db, claims)
    assert user.role == "STUDENT"


def test_auth_me_missing_database_identity_without_email_fails_closed(security):
    response = security.client.get("/auth/me", headers=security.headers(99, ["ADMIN"]))
    assert response.status_code == 401
    assert auth_service.auth_repo.get_by_cognito_sub(security.db, "sub-99") is None


@pytest.mark.parametrize("uid", [1, 4])
def test_different_cognito_subject_cannot_inherit_database_privileges(security, uid, monkeypatch):
    user = security.db.get(User, uid)
    client = Mock()
    client.admin_get_user.return_value = {
        "Enabled": True,
        "UserStatus": "CONFIRMED",
        "UserAttributes": [
            {"Name": "sub", "Value": "sub-99"},
            {"Name": "email", "Value": user.email},
            {"Name": "email_verified", "Value": "true"},
        ],
    }
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)
    claims = {**security.claims(99, ["ADMIN"]), "username": "conflicting-user"}
    with pytest.raises(auth_service.InvalidToken):
        auth_service.sync_authorizer_claims(security.db, claims)
    assert security.db.get(User, uid).cognito_sub == f"sub-{uid}"


@pytest.mark.parametrize("operation", ["put", "delete"])
def test_same_signed_token_loses_flashcard_rights_after_database_demotion(security, operation):
    headers = security.headers(1, ["INSTRUCTOR"])
    assert security.client.get("/auth/me", headers=headers).json()["role"] == "INSTRUCTOR"
    # Execute SQL to avoid proving the policy only through a pre-mutated ORM object.
    security.db.execute(update(User).where(User.id == 1).values(role="STUDENT"))
    security.db.commit()
    kwargs = {"json": {"front": "Tampered", "is_approved": True}} if operation == "put" else {}
    response = security.client.request(operation.upper(), "/lessons/1/flashcards/1",
                                       headers=headers, **kwargs)
    assert response.status_code == 403
    security.db.expire_all()
    assert security.db.get(User, 1).role == "STUDENT"
    card = security.db.get(Flashcard, 1)
    assert card.front == "Original" and card.is_approved is False


@pytest.mark.parametrize("uid", [2, 3, 4])
@pytest.mark.parametrize("operation", ["put", "delete"])
def test_only_instructor_owner_can_modify_flashcard(security, uid, operation):
    kwargs = {"json": {"front": "Tampered", "is_approved": True}} if operation == "put" else {}
    response = security.client.request(operation.upper(), "/lessons/1/flashcards/1",
                                       headers=security.headers(uid), **kwargs)
    assert response.status_code == 403
    security.db.expire_all()
    card = security.db.get(Flashcard, 1)
    assert card.front == "Original" and card.is_approved is False


def test_instructor_owner_can_update_and_approve_flashcard(security):
    response = security.client.put("/lessons/1/flashcards/1", headers=security.headers(1),
                                   json={"front": "Updated", "is_approved": True})
    assert response.status_code == 200
    security.db.expire_all()
    assert security.db.get(Flashcard, 1).front == "Updated"
    assert security.db.get(Flashcard, 1).is_approved is True


def test_instructor_owner_can_delete_flashcard(security):
    response = security.client.delete("/lessons/1/flashcards/1", headers=security.headers(1))
    assert response.status_code == 204
    security.db.expire_all()
    assert security.db.get(Flashcard, 1) is None
    assert security.db.get(Flashcard, 2) is not None


def test_student_can_still_read_approved_flashcards(security):
    security.db.get(Course, 1).status = "PUBLISHED"
    security.db.get(Lesson, 1).status = "PUBLISHED"
    security.db.get(Flashcard, 1).is_approved = True
    security.db.add(Enrollment(student_id=2, course_id=1))
    security.db.commit()
    response = security.client.get("/lessons/1/flashcards", headers=security.headers(2))
    assert response.status_code == 200
    assert [card["id"] for card in response.json()["cards"]] == [1]


@pytest.mark.parametrize("operation", ["put", "delete"])
def test_owner_cannot_modify_card_from_different_lesson(security, operation):
    kwargs = {"json": {"front": "Tampered"}} if operation == "put" else {}
    response = security.client.request(operation.upper(), "/lessons/1/flashcards/2",
                                       headers=security.headers(1), **kwargs)
    assert response.status_code == 404
    assert security.db.get(Flashcard, 2).front == "Original"


def test_admin_cannot_create_flashcard_for_other_instructor(security):
    response = security.client.post("/lessons/1/flashcards", headers=security.headers(4),
                                    json={"front": "Unauthorized", "back": "Answer", "position": 2})
    assert response.status_code == 403
    assert len(security.db.scalars(select(Flashcard)).all()) == 2


@pytest.mark.parametrize("role", ["STUDENT", "INSTRUCTOR"])
def test_last_admin_demotion_is_rejected_before_any_cognito_call(security, role):
    response = security.client.patch("/admin/users/4", headers=security.headers(4),
                                     json={"role": role, "name": "Should not change"})
    assert response.status_code == 409
    security.db.expire_all()
    assert security.db.get(User, 4).role == "ADMIN"
    assert security.db.get(User, 4).name == "User 4"
    security.profile.assert_not_called()
    security.role_sync.assert_not_called()


def test_last_admin_can_edit_profile_without_demotion(security):
    response = security.client.patch("/admin/users/4", headers=security.headers(4),
                                     json={"name": "Renamed", "role": "ADMIN"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json()["role"] == "ADMIN"


def test_role_change_locks_admin_rows_in_order(security):
    statements = []

    def capture(execution):
        if execution.is_select:
            statements.append(str(execution.statement.compile(dialect=postgresql.dialect())))

    event.listen(security.db, "do_orm_execute", capture)
    try:
        response = security.client.patch("/admin/users/4", headers=security.headers(4),
                                         json={"role": "ADMIN"})
    finally:
        event.remove(security.db, "do_orm_execute", capture)
    assert response.status_code == 200
    assert any("users.role =" in sql and "ORDER BY users.id" in sql and "FOR UPDATE" in sql
               for sql in statements), "Role changes must serialize the current admin set"


def test_two_admins_can_demote_one_but_not_both(security):
    security.db.get(User, 3).role = "ADMIN"
    security.db.commit()
    headers = security.headers(4, ["ADMIN"])
    first = security.client.patch("/admin/users/3", headers=headers, json={"role": "STUDENT"})
    assert first.status_code == 200
    second = security.client.patch("/admin/users/4", headers=headers, json={"role": "STUDENT"})
    assert second.status_code == 409
    assert security.db.get(User, 4).role == "ADMIN"
    assert security.db.get(User, 3).role == "STUDENT"


def test_demoted_admin_old_token_cannot_manage_users(security):
    security.db.get(User, 3).role = "ADMIN"
    security.db.commit()
    old_headers = security.headers(3, ["ADMIN"])
    response = security.client.patch("/admin/users/3", headers=security.headers(4),
                                     json={"role": "STUDENT"})
    assert response.status_code == 200
    assert security.client.get("/admin/users", headers=old_headers).status_code == 403
    assert security.db.get(User, 3).role == "STUDENT"


def test_admin_can_step_down_if_another_admin_remains(security):
    security.db.get(User, 3).role = "ADMIN"
    security.db.commit()
    old_headers = security.headers(4, ["ADMIN"])
    response = security.client.patch("/admin/users/4", headers=old_headers,
                                     json={"role": "STUDENT"})
    assert response.status_code == 200
    assert security.db.get(User, 3).role == "ADMIN"
    assert security.client.get("/admin/users", headers=old_headers).status_code == 403


def test_null_role_is_rejected_without_mutation(security):
    response = security.client.patch("/admin/users/4", headers=security.headers(4), json={"role": None})
    assert response.status_code == 422
    security.db.expire_all()
    assert security.db.get(User, 4).role == "ADMIN"
    security.profile.assert_not_called()
    security.role_sync.assert_not_called()


def test_failed_role_sync_rolls_back_database_role(security):
    security.role_sync.side_effect = auth_service.CognitoAuthError("Unavailable", status_code=503)
    response = security.client.patch("/admin/users/1", headers=security.headers(4),
                                     json={"role": "STUDENT"})
    assert response.status_code == 503
    assert security.db.get(User, 1).role == "INSTRUCTOR"


def test_admin_can_disable_and_enable_user_and_response_shows_status(security, monkeypatch):
    sync = Mock()
    monkeypatch.setattr(auth_service, "admin_set_user_enabled", sync)
    response = security.client.patch(
        "/admin/users/2/status", headers=security.headers(4), json={"enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"
    sync.assert_called_once_with(cognito_sub="sub-2", enabled=False)

    sync.reset_mock()
    response = security.client.patch(
        "/admin/users/2/status", headers=security.headers(4), json={"enabled": True}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    sync.assert_called_once_with(cognito_sub="sub-2", enabled=True)


def test_non_admin_cannot_change_account_status(security, monkeypatch):
    sync = Mock()
    monkeypatch.setattr(auth_service, "admin_set_user_enabled", sync)
    response = security.client.patch(
        "/admin/users/1/status", headers=security.headers(2), json={"enabled": False}
    )
    assert response.status_code == 403
    assert security.db.get(User, 1).status == "ACTIVE"
    sync.assert_not_called()


def test_admin_cannot_disable_self_or_remove_last_active_admin(security, monkeypatch):
    sync = Mock()
    monkeypatch.setattr(auth_service, "admin_set_user_enabled", sync)
    self_lock = security.client.patch(
        "/admin/users/4/status", headers=security.headers(4), json={"enabled": False}
    )
    assert self_lock.status_code == 409
    security.db.get(User, 3).role = "ADMIN"
    security.db.commit()
    disable_other_admin = security.client.patch(
        "/admin/users/3/status", headers=security.headers(4), json={"enabled": False}
    )
    assert disable_other_admin.status_code == 200
    assert security.db.get(User, 3).status == "INACTIVE"
    last_admin_demotion = security.client.patch(
        "/admin/users/4", headers=security.headers(4), json={"role": "STUDENT"}
    )
    assert last_admin_demotion.status_code == 409
    assert security.db.get(User, 4).role == "ADMIN"
    sync.assert_called_once_with(cognito_sub="sub-3", enabled=False)


def test_disabled_account_cannot_reuse_an_unexpired_access_token(security):
    security.db.get(User, 2).status = "INACTIVE"
    security.db.commit()
    response = security.client.get("/auth/me", headers=security.headers(2))
    assert response.status_code == 403
    assert response.json()["detail"] == "Account is disabled"


def test_cognito_disable_failure_leaves_rds_unchanged(security, monkeypatch):
    sync = Mock(side_effect=[auth_service.CognitoAuthError("Cognito unavailable", status_code=503), None])
    monkeypatch.setattr(auth_service, "admin_set_user_enabled", sync)
    response = security.client.patch(
        "/admin/users/2/status", headers=security.headers(4), json={"enabled": False}
    )
    assert response.status_code == 503
    assert security.db.get(User, 2).status == "ACTIVE"
    assert [call.kwargs["enabled"] for call in sync.call_args_list] == [False, True]


@pytest.mark.parametrize(("enabled", "operation"), [
    (False, "admin_disable_user"), (True, "admin_enable_user"),
])
def test_cognito_status_service_calls_expected_admin_operation(monkeypatch, enabled, operation):
    client = Mock()
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)
    monkeypatch.setattr(settings, "COGNITO_USER_POOL_ID", "test-pool")
    auth_service.admin_set_user_enabled(cognito_sub="stable-cognito-sub", enabled=enabled)
    getattr(client, operation).assert_called_once_with(
        UserPoolId="test-pool", Username="stable-cognito-sub"
    )


def test_status_sync_uses_cognito_sub_even_when_email_changes(security, monkeypatch):
    user = security.db.get(User, 2)
    user.email = "changed-address@example.com"
    security.db.commit()
    sync = Mock()
    monkeypatch.setattr(auth_service, "admin_set_user_enabled", sync)

    response = security.client.patch(
        "/admin/users/2/status", headers=security.headers(4), json={"enabled": False}
    )

    assert response.status_code == 200
    sync.assert_called_once_with(cognito_sub="sub-2", enabled=False)


def test_cognito_failure_and_failed_restore_reports_possible_drift(security, monkeypatch):
    sync = Mock(side_effect=[auth_service.CognitoAuthError("timeout", status_code=503),
                             auth_service.CognitoAuthError("restore failed", status_code=503)])
    monkeypatch.setattr(auth_service, "admin_set_user_enabled", sync)
    response = security.client.patch(
        "/admin/users/2/status", headers=security.headers(4), json={"enabled": False}
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ACCOUNT_SYNC_INCONSISTENT"
    assert security.db.get(User, 2).status == "ACTIVE"
    assert sync.call_count == 2


def test_database_failure_compensates_cognito_status(security, monkeypatch):
    sync = Mock()
    monkeypatch.setattr(auth_service, "admin_set_user_enabled", sync)
    original_commit = security.db.commit
    failed = False

    def fail_once():
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("simulated database failure")
        original_commit()

    monkeypatch.setattr(security.db, "commit", fail_once)
    response = security.client.patch(
        "/admin/users/2/status", headers=security.headers(4), json={"enabled": False}
    )
    assert response.status_code == 500
    assert security.db.get(User, 2).status == "ACTIVE"
    assert [call.kwargs["enabled"] for call in sync.call_args_list] == [False, True]


def test_failed_cognito_compensation_reports_possible_drift(security, monkeypatch):
    sync = Mock(side_effect=[None, auth_service.CognitoAuthError("rollback failed", status_code=503)])
    monkeypatch.setattr(auth_service, "admin_set_user_enabled", sync)
    original_commit = security.db.commit
    monkeypatch.setattr(security.db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    response = security.client.patch(
        "/admin/users/2/status", headers=security.headers(4), json={"enabled": False}
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ACCOUNT_SYNC_INCONSISTENT"
    assert security.db.get(User, 2).status == "ACTIVE"
    assert sync.call_count == 2


@pytest.mark.parametrize("changes", [{"exp": 0}, {"iss": "wrong"},
                                     {"client_id": "wrong"}, {"token_use": "id"}])
def test_invalid_jwt_still_rejected(security, changes):
    token = security.token(1, ["INSTRUCTOR"], **changes)
    assert security.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_invalid_signature_still_rejected(security):
    token = jwt.encode(security.claims(1), rsa.generate_private_key(public_exponent=65537, key_size=2048),
                       algorithm="RS256")
    assert security.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_demo_header_does_not_authenticate_or_override_jwt(security):
    assert security.client.get("/auth/me", headers={"X-Demo-User": "4"}).status_code == 401
    response = security.client.get("/admin/users", headers={**security.headers(2), "X-Demo-User": "4"})
    assert response.status_code == 403
