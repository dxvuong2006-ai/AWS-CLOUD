import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-" * 4
os.environ["COGNITO_REGION"] = "ap-southeast-1"
os.environ["COGNITO_USER_POOL_ID"] = "ap-southeast-1_testpool"
os.environ["COGNITO_APP_CLIENT_ID"] = "test-client"

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError
import httpx
from fastapi import Depends, FastAPI

from app.api.auth import router
from app.dependencies import get_db, require_instructor, require_admin, require_student
from app.services import auth_service


class AuthHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users = {
            i: SimpleNamespace(
                id=i,
                cognito_sub=f"cognito-{i}",
                name=role,
                email=f"{role.lower()}@example.com",
                role=role,
                password_hash=None,
                created_at=None,
            )
            for i, role in enumerate(["STUDENT", "INSTRUCTOR", "ADMIN"], 1)
        }
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: object()

        @app.get("/student")
        def student(user=Depends(require_student)):
            return {"id": user.id}

        @app.get("/instructor")
        def instructor(user=Depends(require_instructor)):
            return {"id": user.id}

        @app.get("/admin")
        def admin(user=Depends(require_admin)):
            return {"id": user.id}

        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

        def token_user(db, token):
            if not token.startswith("cognito-token-"):
                raise auth_service.InvalidToken()
            uid = int(token.removeprefix("cognito-token-"))
            return self.users[uid]

        self.token_user = patch.object(
            auth_service,
            "user_from_access_token",
            side_effect=token_user,
        )
        self.token_user.start()

    async def asyncTearDown(self):
        await self.client.aclose()
        self.token_user.stop()

    async def token(self, uid):
        return f"cognito-token-{uid}"

    async def test_access_token_me_and_role_matrix(self):
        role_paths = {
            1: "student",
            2: "instructor",
            3: "admin",
        }
        for uid, role_path in role_paths.items():
            token = await self.token(uid)
            headers = {"Authorization": f"Bearer {token}"}
            me = await self.client.get("/auth/me", headers=headers)
            self.assertEqual(me.status_code, 200)

            for path in ["student", "instructor", "admin"]:
                result = await self.client.get("/" + path, headers=headers)
                self.assertEqual(result.status_code, 200 if path == role_path else 403)

    async def test_backend_login_proxy_is_removed(self):
        response = await self.client.post(
            "/auth/login",
            json={"email": "student@example.com", "password": "Password123!"},
        )
        self.assertEqual(response.status_code, 404)

    async def test_missing_and_invalid_tokens_rejected(self):
        for headers in [
            {},
            {"X-Demo-User": "3"},
            {"Authorization": "Bearer invalid"},
            {"Authorization": "Basic anything"},
        ]:
            response = await self.client.get("/auth/me", headers=headers)
            self.assertEqual(response.status_code, 401)

    async def test_role_is_read_from_database(self):
        self.users[3].role = "STUDENT"
        response = await self.client.get(
            "/admin",
            headers={"Authorization": "Bearer cognito-token-3", "X-Demo-User": "3"},
        )
        self.assertEqual(response.status_code, 403)


class CognitoTokenVerificationLoggingTests(unittest.TestCase):
    def test_access_token_sync_uses_verified_claims_without_cognito_api_calls(self):
        signing_key = SimpleNamespace(key="test-key")
        claims = {
            "token_use": "access",
            "client_id": "test-client",
            "iss": "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_testpool",
            "sub": "cognito-1",
        }
        user = SimpleNamespace(
            id=1,
            cognito_sub="cognito-1",
            name="Student",
            email="student@example.com",
            role="STUDENT",
            password_hash=None,
        )
        db = Mock()
        with patch.object(
            auth_service.jwt,
            "PyJWKClient",
            return_value=SimpleNamespace(
                get_signing_key_from_jwt=lambda _: signing_key
            ),
        ), patch.object(
            auth_service.jwt,
            "decode",
            return_value=claims,
        ), patch.object(
            auth_service.auth_repo,
            "get_by_cognito_sub",
            return_value=user,
        ), patch.object(
            auth_service,
            "cognito_client",
        ) as cognito_client:
            result = auth_service.user_from_access_token(db, "valid.access.token")

        self.assertIs(result, user)
        cognito_client.assert_not_called()
        db.commit.assert_called_once()

    def test_signature_error_is_logged_without_token(self):
        token = "sensitive.jwt.token"
        jwk_client = patch.object(
            auth_service.jwt,
            "PyJWKClient",
            return_value=SimpleNamespace(
                get_signing_key_from_jwt=lambda _: (_ for _ in ()).throw(
                    auth_service.jwt.InvalidSignatureError()
                )
            ),
        )
        with jwk_client, self.assertLogs(
            "app.services.auth_service",
            level="WARNING",
        ) as captured:
            with self.assertRaises(auth_service.InvalidToken):
                auth_service.user_from_access_token(object(), token)

        log_output = "\n".join(captured.output)
        self.assertIn("exception_type=InvalidSignatureError", log_output)
        self.assertNotIn(token, log_output)

    def test_client_id_mismatch_is_logged_as_claim_reason(self):
        signing_key = SimpleNamespace(key="test-key")
        claims = {
            "token_use": "access",
            "client_id": "different-client",
        }
        with patch.object(
            auth_service.jwt.PyJWKClient,
            "__init__",
            return_value=None,
        ), patch.object(
            auth_service.jwt.PyJWKClient,
            "get_signing_key_from_jwt",
            return_value=signing_key,
        ), patch.object(
            auth_service.jwt,
            "decode",
            return_value=claims,
        ), self.assertLogs(
            "app.services.auth_service",
            level="WARNING",
        ) as captured:
            with self.assertRaises(auth_service.InvalidToken):
                auth_service.user_from_access_token(object(), "sensitive.jwt.token")

        log_output = "\n".join(captured.output)
        self.assertIn("reason=client_id_mismatch", log_output)
        self.assertNotIn("sensitive.jwt.token", log_output)


class CognitoEmailVerificationTests(unittest.TestCase):
    def test_confirmed_cognito_user_can_finish_local_sync_after_retry(self):
        email = "student@example.com"
        cognito = Mock()
        cognito.confirm_sign_up.side_effect = ClientError(
            {
                "Error": {
                    "Code": "NotAuthorizedException",
                    "Message": "User cannot be confirmed. Current status is CONFIRMED.",
                }
            },
            "ConfirmSignUp",
        )
        cognito.admin_get_user.return_value = {
            "UserStatus": "CONFIRMED",
            "UserAttributes": [
                {"Name": "sub", "Value": "cognito-student"},
                {"Name": "email", "Value": email},
                {"Name": "name", "Value": "Student"},
            ],
        }
        db = Mock()
        created_user = SimpleNamespace(
            cognito_sub="cognito-student",
            email=email,
            name="Student",
            password_hash=None,
        )

        with patch.object(auth_service, "cognito_client", return_value=cognito), patch.object(
            auth_service.auth_repo,
            "get_by_cognito_sub",
            return_value=None,
        ), patch.object(
            auth_service.auth_repo,
            "get_by_email",
            return_value=None,
        ), patch.object(
            auth_service.auth_repo,
            "create_cognito_user",
            return_value=created_user,
        ) as create_user:
            result = auth_service.verify_email(db, email, "123456")

        self.assertEqual(result, {"message": "Đã xác minh email."})
        cognito.admin_get_user.assert_called_once_with(
            UserPoolId="ap-southeast-1_testpool",
            Username=email,
        )
        create_user.assert_called_once_with(
            db,
            cognito_sub="cognito-student",
            name="Student",
            email=email,
            role="STUDENT",
        )

    def test_confirmation_errors_other_than_already_confirmed_are_not_ignored(self):
        cognito = Mock()
        cognito.confirm_sign_up.side_effect = ClientError(
            {
                "Error": {
                    "Code": "CodeMismatchException",
                    "Message": "Invalid confirmation code.",
                }
            },
            "ConfirmSignUp",
        )

        with patch.object(auth_service, "cognito_client", return_value=cognito):
            with self.assertRaises(auth_service.CognitoAuthError) as raised:
                auth_service.verify_email(Mock(), "student@example.com", "000000")

        self.assertEqual(raised.exception.code, "CodeMismatchException")
        cognito.admin_get_user.assert_not_called()


if __name__ == "__main__":
    unittest.main()
