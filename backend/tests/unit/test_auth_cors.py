import os
import unittest

import httpx

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-" * 4
os.environ["COGNITO_REGION"] = "ap-southeast-1"
os.environ["COGNITO_USER_POOL_ID"] = "ap-southeast-1_testpool"
os.environ["COGNITO_APP_CLIENT_ID"] = "test-client"

from app.main import app


class AuthCorsTests(unittest.IsolatedAsyncioTestCase):
    async def test_production_frontend_can_preflight_public_auth_route(self):
        origin = "https://d1my2q1fj0jxmb.cloudfront.net"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.options(
                "/auth/forgot-password",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)
        self.assertIn("POST", response.headers["access-control-allow-methods"])
