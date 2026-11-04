"""HTTP auth tests with repository doubles; no live database is accessed."""
import os
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/unused_auth_test"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-" * 4

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
import httpx
import jwt
from fastapi import Depends, FastAPI
from app.api.auth import router
from app.dependencies import get_db, require_instructor, require_admin, require_student
from app.services import auth_service
from app.config import settings

class AuthHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users = {
            i: SimpleNamespace(id=i, name=role, email=f"{role.lower()}@example.com",
                               role=role, password_hash=auth_service.hash_password("Password123!"),
                               created_at=None)
            for i, role in enumerate(["STUDENT", "INSTRUCTOR", "ADMIN"], 1)
        }
        self.by_id = patch.object(auth_service.auth_repo, "get_by_id",
                                  side_effect=lambda db, uid: self.users.get(uid))
        self.by_email = patch.object(auth_service.auth_repo, "get_by_email",
            side_effect=lambda db, email: next((u for u in self.users.values() if u.email == email.lower()), None))
        self.by_id.start()
        self.by_email.start()
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

    async def asyncTearDown(self):
        await self.client.aclose()
        self.by_id.stop()
        self.by_email.stop()

    async def token(self, uid):
        response = await self.client.post("/auth/login", json={
            "email": self.users[uid].email, "password": "Password123!"
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("password_hash", response.json()["user"])
        return response.json()["access_token"]

    async def test_login_me_and_role_matrix(self):
        for uid, role in [(1, "student"), (2, "instructor"), (3, "admin")]:
            token = await self.token(uid)
            headers = {"Authorization": f"Bearer {token}"}
            me = await self.client.get("/auth/me", headers=headers)
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["id"], uid)
            for path in ["student", "instructor", "admin"]:
                result = await self.client.get("/" + path, headers=headers)
                self.assertEqual(result.status_code, 200 if path == role else 403)

    async def test_missing_demo_and_invalid_tokens_rejected(self):
        for headers in [{}, {"X-Demo-User": "3"}, {"Authorization": "Bearer invalid"},
                        {"Authorization": "Basic anything"}]:
            response = await self.client.get("/auth/me", headers=headers)
            self.assertEqual(response.status_code, 401)
        bad = await self.client.post("/auth/login", json={
            "email": self.users[1].email, "password": "wrong"
        })
        self.assertEqual(bad.status_code, 401)

    async def test_expired_wrong_signature_and_deleted_user(self):
        good = await self.token(1)
        payload = jwt.decode(good, options={"verify_signature": False})
        payload["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        expired = jwt.encode(payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm="HS256")
        wrong = jwt.encode(payload, "wrong-test-secret-" * 4, algorithm="HS256")
        for token in [expired, wrong]:
            response = await self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 401)
        self.users.pop(1)
        response = await self.client.get("/auth/me", headers={"Authorization": f"Bearer {good}"})
        self.assertEqual(response.status_code, 401)

    async def test_role_is_read_from_database(self):
        token = await self.token(3)
        self.users[3].role = "STUDENT"
        response = await self.client.get("/admin", headers={"Authorization": f"Bearer {token}", "X-Demo-User": "3"})
        self.assertEqual(response.status_code, 403)

if __name__ == "__main__":
    unittest.main()
