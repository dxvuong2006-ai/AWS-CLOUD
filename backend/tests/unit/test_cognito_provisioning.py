"""Safe Cognito-to-RDS provisioning regressions; no live AWS or RDS calls."""

import json
from pathlib import Path
import re

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router
from app.config import settings
from app.dependencies import get_db
from app.models.user import User
from app.repositories import auth_repo
from app.schemas.auth import RegisterRequest
from app.services import auth_service


@pytest.fixture
def cognito_settings(monkeypatch):
    monkeypatch.setattr(settings, "COGNITO_REGION", "ap-southeast-1")
    monkeypatch.setattr(settings, "COGNITO_USER_POOL_ID", "ap-southeast-1_testpool")
    monkeypatch.setattr(settings, "COGNITO_APP_CLIENT_ID", "test-client")


def claims(sub: str, **changes):
    return {
        "sub": sub,
        "token_use": "access",
        "client_id": "test-client",
        "iss": (
            "https://cognito-idp.ap-southeast-1.amazonaws.com/"
            "ap-southeast-1_testpool"
        ),
        **changes,
    }


def cognito_profile(
    sub: str,
    email: str,
    name: str = "New student",
    *,
    email_verified: bool = True,
    enabled: bool = True,
    user_status: str = "CONFIRMED",
):
    return {
        "Enabled": enabled,
        "UserStatus": user_status,
        "UserAttributes": [
            {"Name": "sub", "Value": sub},
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": str(email_verified).lower()},
            {"Name": "name", "Value": name},
        ],
    }


def test_signup_starts_cognito_but_waits_for_verified_identity(
    db_session, monkeypatch, cognito_settings
):
    client = Mock()
    client.sign_up.return_value = {
        "UserConfirmed": False,
        "CodeDeliveryDetails": {"DeliveryMedium": "EMAIL"},
    }
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)

    result = auth_service.register_student(
        db_session,
        RegisterRequest(
            name="Pending student",
            email="pending@example.com",
            password="Valid-password-123!",
        ),
    )

    assert result["verification_required"] is True
    assert db_session.query(User).count() == 0
    client.sign_up.assert_called_once()


def test_signup_existing_rds_email_never_calls_cognito(
    db_session, monkeypatch, cognito_settings
):
    db_session.add(
        User(
            cognito_sub="existing-sub",
            name="Existing",
            email="existing@example.com",
            role="INSTRUCTOR",
        )
    )
    db_session.commit()
    client = Mock(side_effect=AssertionError("Cognito must not be called"))
    monkeypatch.setattr(auth_service, "cognito_client", client)

    with pytest.raises(auth_service.CognitoAuthError) as captured:
        auth_service.register_student(
            db_session,
            RegisterRequest(
                name="Replacement",
                email="EXISTING@example.com",
                password="Valid-password-123!",
            ),
        )

    assert captured.value.code == "EMAIL_EXISTS"
    assert captured.value.status_code == 409
    client.assert_not_called()


def test_auth_me_provisions_access_token_without_email_once(
    db_session, monkeypatch, cognito_settings
):
    client = Mock()
    client.admin_get_user.return_value = cognito_profile(
        "new-sub", "Missing.Profile@Example.com"
    )
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)
    token_claims = claims("new-sub", username="cognito-internal-username")
    monkeypatch.setattr(
        auth_service,
        "user_from_access_token",
        lambda db, _token: auth_service.sync_authorizer_claims(db, token_claims),
    )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as http:
        first = http.get("/auth/me", headers={"Authorization": "Bearer signed-token"})
        second = http.get("/auth/me", headers={"Authorization": "Bearer signed-token"})

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    user = db_session.query(User).filter_by(cognito_sub="new-sub").one()
    assert (user.email, user.role, user.name) == (
        "missing.profile@example.com",
        "STUDENT",
        "New student",
    )
    assert db_session.query(User).filter_by(cognito_sub="new-sub").count() == 1
    client.admin_get_user.assert_called_once_with(
        UserPoolId="ap-southeast-1_testpool",
        Username="cognito-internal-username",
    )


def test_existing_profile_is_read_only_and_ignores_groups(
    db_session, monkeypatch, cognito_settings
):
    original = User(
        cognito_sub="existing-sub",
        name="RDS managed name",
        email="rds@example.com",
        role="INSTRUCTOR",
        password_hash="preserve-local-hash",
    )
    db_session.add(original)
    db_session.commit()
    forbidden_client = Mock(side_effect=AssertionError("existing users need no AWS call"))
    monkeypatch.setattr(auth_service, "cognito_client", forbidden_client)

    result = auth_service.sync_authorizer_claims(
        db_session,
        claims(
            "existing-sub",
            email="changed-in-cognito@example.com",
            name="Changed name",
            **{"cognito:groups": ["ADMIN"]},
        ),
    )

    db_session.refresh(original)
    assert result.id == original.id
    assert (
        original.cognito_sub,
        original.name,
        original.email,
        original.role,
        original.password_hash,
    ) == (
        "existing-sub",
        "RDS managed name",
        "rds@example.com",
        "INSTRUCTOR",
        "preserve-local-hash",
    )
    forbidden_client.assert_not_called()


@pytest.mark.parametrize(
    "profile",
    [
        cognito_profile(
            "blocked-sub", "blocked@example.com", email_verified=False
        ),
        cognito_profile(
            "blocked-sub",
            "blocked@example.com",
            user_status="FORCE_CHANGE_PASSWORD",
        ),
        cognito_profile(
            "blocked-sub", "blocked@example.com", enabled=False
        ),
    ],
    ids=["email-unverified", "force-change-password", "disabled"],
)
def test_first_login_rejects_unprovisionable_cognito_state(
    db_session, monkeypatch, cognito_settings, profile
):
    client = Mock()
    client.admin_get_user.return_value = profile
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)

    with pytest.raises(auth_service.InvalidToken):
        auth_service.sync_authorizer_claims(
            db_session,
            claims(
                "blocked-sub",
                username="blocked-cognito-username",
                # Even forged/customized claims cannot bypass AdminGetUser.
                email="verified-looking-claim@example.com",
            ),
        )

    assert db_session.query(User).count() == 0


@pytest.mark.parametrize(
    "profile",
    [
        cognito_profile(
            "blocked-verify-sub", "blocked-verify@example.com", email_verified=False
        ),
        cognito_profile(
            "blocked-verify-sub",
            "blocked-verify@example.com",
            user_status="FORCE_CHANGE_PASSWORD",
        ),
    ],
    ids=["email-unverified", "force-change-password"],
)
def test_verify_email_rejects_unprovisionable_cognito_state(
    db_session, monkeypatch, cognito_settings, profile
):
    client = Mock()
    client.admin_get_user.return_value = profile
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)

    with pytest.raises(auth_service.CognitoAuthError) as captured:
        auth_service.verify_email(
            db_session, "blocked-verify@example.com", "123456"
        )

    assert captured.value.code == "COGNITO_PROFILE_INVALID"
    assert db_session.query(User).count() == 0


def test_different_subject_never_claims_matching_email_or_id_10(
    db_session, cognito_settings
):
    conflicted = User(
        id=10,
        cognito_sub="old-sub-on-id-10",
        name="Keep this profile",
        email="vuongthuy1998@gmail.com",
        role="ADMIN",
        password_hash="keep-this-too",
    )
    db_session.add(conflicted)
    db_session.commit()

    with pytest.raises(auth_service.InvalidToken):
        auth_service.sync_authorizer_claims(
            db_session,
            claims(
                "current-cognito-sub",
                email="vuongthuy1998@gmail.com",
                name="Cognito name",
                **{"cognito:groups": ["ADMIN"]},
            ),
        )

    db_session.refresh(conflicted)
    assert (
        conflicted.id,
        conflicted.cognito_sub,
        conflicted.name,
        conflicted.role,
        conflicted.password_hash,
    ) == (
        10,
        "old-sub-on-id-10",
        "Keep this profile",
        "ADMIN",
        "keep-this-too",
    )
    assert db_session.query(User).count() == 1


def test_verify_retry_repairs_confirmed_cognito_without_duplicate(
    db_session, monkeypatch, cognito_settings
):
    already_confirmed = ClientError(
        {
            "Error": {
                "Code": "NotAuthorizedException",
                "Message": "User cannot be confirmed. Current status is CONFIRMED",
            }
        },
        "ConfirmSignUp",
    )
    client = Mock()
    client.confirm_sign_up.side_effect = already_confirmed
    client.admin_get_user.return_value = cognito_profile(
        "confirmed-sub", "confirmed@example.com"
    )
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)

    first = auth_service.verify_email(db_session, "confirmed@example.com", "123456")
    user = db_session.query(User).filter_by(cognito_sub="confirmed-sub").one()
    user.name = "RDS name must survive retry"
    user.role = "INSTRUCTOR"
    db_session.commit()
    second = auth_service.verify_email(db_session, "confirmed@example.com", "123456")

    assert first == second
    assert db_session.query(User).filter_by(cognito_sub="confirmed-sub").count() == 1
    db_session.refresh(user)
    assert (user.name, user.role) == ("RDS name must survive retry", "INSTRUCTOR")


def test_uniqueness_race_accepts_only_exact_winner(
    db_session, monkeypatch, cognito_settings
):
    identity = {
        "sub": "race-sub",
        "email": "race@example.com",
        "name": "Race winner",
    }

    def concurrent_winner(db, **values):
        db.add(User(**values))
        db.commit()
        raise auth_repo.EmailAlreadyExists()

    monkeypatch.setattr(auth_repo, "create_cognito_user", concurrent_winner)
    result = auth_service.ensure_cognito_profile(db_session, identity)

    assert result.cognito_sub == "race-sub"
    assert result.email == "race@example.com"
    assert db_session.query(User).count() == 1


def test_lookup_race_accepts_email_row_only_with_exact_subject(
    db_session, monkeypatch, cognito_settings
):
    winner = User(
        cognito_sub="lookup-race-sub",
        name="Concurrent winner",
        email="lookup-race@example.com",
        role="STUDENT",
    )
    db_session.add(winner)
    db_session.commit()
    original_subject_lookup = auth_repo.get_by_cognito_sub
    calls = 0

    def stale_first_subject_lookup(db, sub):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return original_subject_lookup(db, sub)

    monkeypatch.setattr(auth_repo, "get_by_cognito_sub", stale_first_subject_lookup)
    result = auth_service.ensure_cognito_profile(
        db_session,
        {
            "sub": "lookup-race-sub",
            "email": "lookup-race@example.com",
            "name": "Ignored",
        },
    )

    assert result.id == winner.id
    assert (winner.name, winner.role) == ("Concurrent winner", "STUDENT")


def test_verify_rejects_same_email_with_different_subject(
    db_session, monkeypatch, cognito_settings
):
    existing = User(
        cognito_sub="old-sub",
        name="Existing",
        email="collision@example.com",
        role="ADMIN",
    )
    db_session.add(existing)
    db_session.commit()
    client = Mock()
    client.admin_get_user.return_value = cognito_profile(
        "new-sub", "collision@example.com", name="Replacement"
    )
    monkeypatch.setattr(auth_service, "cognito_client", lambda: client)

    with pytest.raises(auth_service.CognitoAuthError) as captured:
        auth_service.verify_email(db_session, "collision@example.com", "123456")

    assert captured.value.code == "IDENTITY_CONFLICT"
    assert captured.value.status_code == 409
    db_session.refresh(existing)
    assert (existing.cognito_sub, existing.name, existing.role) == (
        "old-sub",
        "Existing",
        "ADMIN",
    )


def test_cognito_iam_policy_exactly_covers_admin_api_calls():
    root = Path(__file__).resolve().parents[3]
    source = (root / "backend/app/services/auth_service.py").read_text(encoding="utf-8")
    policy = json.loads(
        (root / "infrastructure/iam/lambda-auth-cognito-permissions.json").read_text(
            encoding="utf-8"
        )
    )
    method_to_action = {
        "admin_get_user": "cognito-idp:AdminGetUser",
        "admin_create_user": "cognito-idp:AdminCreateUser",
        "admin_set_user_password": "cognito-idp:AdminSetUserPassword",
        "admin_add_user_to_group": "cognito-idp:AdminAddUserToGroup",
        "admin_remove_user_from_group": "cognito-idp:AdminRemoveUserFromGroup",
        "admin_update_user_attributes": "cognito-idp:AdminUpdateUserAttributes",
        "admin_disable_user": "cognito-idp:AdminDisableUser",
        "admin_enable_user": "cognito-idp:AdminEnableUser",
    }
    called_admin_methods = set(re.findall(r"\.((?:admin_)[a-z_]+)\(", source))
    policy_actions = {
        action
        for statement in policy["Statement"]
        for action in statement["Action"]
    }

    assert called_admin_methods == set(method_to_action)
    assert policy_actions == set(method_to_action.values())
    assert all(
        statement["Resource"]
        == "arn:aws:cognito-idp:${AWS_REGION}:${ACCOUNT_ID}:userpool/${COGNITO_USER_POOL_ID}"
        for statement in policy["Statement"]
    )
