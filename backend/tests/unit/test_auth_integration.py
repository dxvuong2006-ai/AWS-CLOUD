import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-" * 4
os.environ["COGNITO_REGION"] = "ap-southeast-1"
os.environ["COGNITO_USER_POOL_ID"] = "ap-southeast-1_testpool"
os.environ["COGNITO_APP_CLIENT_ID"] = "test-client"

import unittest
from types import SimpleNamespace
from unittest.mock import patch
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

        self.authenticate = patch.object(
            auth_service,
            "authenticate",
            side_effect=lambda db, email, password: {
                "access_token": "cognito-token-1",
                "expires_in": 3600,
            },
        )
        self.authenticate.start()

        self.sync_login = patch.object(
            auth_service,
            "sync_authenticated_user",
            side_effect=lambda db, token, email: self.users[1],
        )
        self.sync_login.start()

    async def asyncTearDown(self):
        await self.client.aclose()
        self.sync_login.stop()
        self.authenticate.stop()
        self.token_user.stop()

    async def token(self, uid):
        email = self.users[uid].email
        response = await self.client.post("/auth/login", json={"email": email, "password": "Password123!"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("password_hash", response.json()["user"])
        return f"cognito-token-{uid}"

    async def test_login_me_and_role_matrix(self):
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


if __name__ == "__main__":
    unittest.main()
