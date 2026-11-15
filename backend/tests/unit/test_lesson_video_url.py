"""Offline API tests: repository doubles, real access checks and SigV4, stubbed S3 HEAD.

Run from backend: python -m unittest discover -s tests/unit -p test_lesson_video_url.py -v
"""
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, unquote, urlsplit

import boto3
import httpx
from fastapi import HTTPException, Request
from botocore.config import Config
from botocore.exceptions import EndpointConnectionError, NoCredentialsError, ProfileNotFound, SSLError
from botocore.stub import Stubber

from app.config import Settings, settings
from app import config
from app.dependencies import get_current_user, get_db
from app.main import app


class LessonVideoUrlTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.user = SimpleNamespace(id=1, role="INSTRUCTOR")
        self.db = Mock()
        self.db.info = {"upload_ledger_available": True}
        self.db.query.return_value.filter.return_value.first.return_value = self.user
        self.db.query.return_value.filter_by.return_value.populate_existing.return_value.limit.return_value.all.return_value = []
        self.db.query.return_value.filter.return_value.populate_existing.return_value.limit.return_value.all.return_value = []
        app.dependency_overrides[get_db] = lambda: self.db
        def current_user(request: Request):
            demo_user = request.headers.get("X-Demo-User")
            if demo_user == "invalid":
                raise HTTPException(status_code=400, detail="Invalid demo user")
            if demo_user == "999999":
                raise HTTPException(status_code=401, detail="Authentication required")
            return self.user
        app.dependency_overrides[get_current_user] = current_user
        self.addCleanup(app.dependency_overrides.clear)
        self.lesson = SimpleNamespace(
            id=8, section_id=4, raw_video_key="lessons/8/raw/test video.mp4",
            processed_video_key=None, status="PUBLISHED", retry_count=0,
        )
        self.course = SimpleNamespace(id=2, instructor_id=1, status="PUBLISHED")
        self.repo = {}
        for name, value in {
            "get_by_id": self.lesson,
            "get_section": SimpleNamespace(id=4, course_id=2),
            "get_course": self.course,
            "has_enrollment": True,
        }.items():
            self.repo[name] = self.stack.enter_context(patch(
                f"app.repositories.lessons_repo.{name}", return_value=value
            ))
        self.stack.enter_context(patch(
            "app.services.unlock_service.assert_section_unlocked"
        ))
        self.stack.enter_context(patch(
            "app.repositories.courses_repo.lock_by_id", return_value=self.course
        ))
        self.stack.enter_context(patch(
            "app.repositories.lessons_repo.lock_by_id", return_value=self.lesson
        ))
        self.stack.enter_context(patch.object(settings, "APP_ENV", "development"))
        self.stack.enter_context(patch.object(settings, "ALLOW_RAW_VIDEO_PLAYBACK", True))
        self.stack.enter_context(patch.object(settings, "VIDEO_URL_EXPIRES_IN", 900))
        # Deliberately fake credentials are only used for offline signing tests.
        self.s3 = boto3.client(
            "s3", region_name="ap-southeast-1",
            aws_access_key_id="testing", aws_secret_access_key="testing",
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
        self.factory = self.stack.enter_context(patch(
            "app.adapters.storage.s3_storage.boto3.client", return_value=self.s3
        ))
        self.stub = self.stack.enter_context(Stubber(self.s3))

    async def get(self, path="/lessons/8/video-url", **kwargs):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path, **kwargs)

    def head_ok(self, key=None):
        self.stub.add_response("head_object", {"ContentType": "application/octet-stream"}, {
            "Bucket": settings.S3_BUCKET, "Key": key or self.lesson.raw_video_key,
        })

    async def test_raw_database_key_generates_sigv4_get_and_ignores_client_key(self):
        self.head_ok()
        with patch.object(self.s3, "generate_presigned_url", wraps=self.s3.generate_presigned_url) as sign:
            response = await self.get("/lessons/8/video-url?object_key=attacker.mp4")
        sign.assert_called_once_with(
            ClientMethod="get_object",
            Params={
                "Bucket": settings.S3_BUCKET, "Key": self.lesson.raw_video_key,
                "ResponseContentType": "video/mp4", "ResponseContentDisposition": "inline",
            },
            ExpiresIn=900, HttpMethod="GET",
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(set(data), {"lesson_id", "video_url", "expires_in", "content_type"})
        self.assertEqual((data["lesson_id"], data["expires_in"], data["content_type"]), (8, 900, "video/mp4"))
        url = urlsplit(data["video_url"])
        self.assertEqual(unquote(url.path), "/" + self.lesson.raw_video_key)
        query = parse_qs(url.query)
        self.assertEqual(query["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
        self.assertIn("/ap-southeast-1/s3/aws4_request", query["X-Amz-Credential"][0])
        self.assertEqual(query["X-Amz-Expires"], ["900"])
        self.assertEqual(query["response-content-type"], ["video/mp4"])
        self.assertEqual(query["response-content-disposition"], ["inline"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.repo["get_by_id"].assert_called_once_with(self.db, 8)
        self.assertEqual(self.factory.call_args.kwargs["config"].signature_version, "s3v4")
        self.stub.assert_no_pending_responses()

    async def test_processed_video_preferred_and_allowed_in_production(self):
        settings.APP_ENV = "production"
        self.lesson.processed_video_key = "lessons/8/processed/video.mp4"
        self.head_ok(self.lesson.processed_video_key)
        response = await self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(unquote(urlsplit(response.json()["video_url"]).path), "/" + self.lesson.processed_video_key)

    async def test_production_never_uses_raw_even_when_flag_true(self):
        settings.APP_ENV = "production"
        response = await self.get()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "VIDEO_NOT_AVAILABLE")
        self.factory.assert_not_called()

    async def test_development_requires_explicit_raw_flag(self):
        settings.ALLOW_RAW_VIDEO_PLAYBACK = False
        self.assertEqual((await self.get()).status_code, 404)
        self.factory.assert_not_called()

    async def test_no_attached_video(self):
        self.lesson.raw_video_key = None
        response = await self.get()
        self.assertEqual(response.json()["code"], "VIDEO_NOT_AVAILABLE")
        self.assertEqual(response.status_code, 404)
        self.factory.assert_not_called()

    async def test_missing_lesson(self):
        self.repo["get_by_id"].return_value = None
        self.assertEqual((await self.get()).status_code, 404)
        self.factory.assert_not_called()

    async def test_instructor_cannot_access_another_course(self):
        self.course.instructor_id = 99
        self.assertEqual((await self.get()).status_code, 403)
        self.factory.assert_not_called()

    async def test_student_requires_enrollment(self):
        self.user.role = "STUDENT"
        self.repo["has_enrollment"].return_value = False
        self.assertEqual((await self.get()).status_code, 403)
        self.factory.assert_not_called()

    async def test_student_requires_published_course(self):
        self.user.role = "STUDENT"
        self.course.status = "DRAFT"
        self.assertEqual((await self.get()).status_code, 403)
        self.factory.assert_not_called()

    async def test_enrolled_student_can_play(self):
        self.user.role = "STUDENT"
        self.head_ok()
        self.assertEqual((await self.get()).status_code, 200)

    async def test_unknown_role_is_denied(self):
        self.user.role = "ADMIN"
        self.assertEqual((await self.get()).status_code, 403)
        self.factory.assert_not_called()

    async def test_invalid_identity_is_denied_by_existing_dependency(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        self.assertEqual((await self.get(headers={"X-Demo-User": "999999"})).status_code, 401)
        self.factory.assert_not_called()

    async def test_invalid_demo_header(self):
        self.assertEqual((await self.get(headers={"X-Demo-User": "invalid"})).status_code, 400)
        self.factory.assert_not_called()

    async def test_non_mp4_is_rejected(self):
        self.lesson.raw_video_key = "lessons/8/raw/video.mov"
        response = await self.get()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "VIDEO_FORMAT_UNSUPPORTED")
        self.factory.assert_not_called()

    async def test_missing_object(self):
        self.stub.add_client_error("head_object", service_error_code="404", http_status_code=404)
        response = await self.get()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "VIDEO_OBJECT_NOT_FOUND")
        self.assertNotIn("video_url", response.json())

    async def test_s3_access_denied(self):
        self.stub.add_client_error("head_object", service_error_code="AccessDenied", http_status_code=403)
        response = await self.get()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "VIDEO_STORAGE_ACCESS_DENIED")
        self.assertNotIn(self.lesson.raw_video_key, response.text)

    async def test_s3_unavailable(self):
        self.stub.add_client_error("head_object", service_error_code="SlowDown", http_status_code=503)
        response = await self.get()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "VIDEO_STORAGE_UNAVAILABLE")

    async def test_missing_bucket_is_an_upstream_error_not_a_missing_video(self):
        self.stub.add_client_error("head_object", service_error_code="NoSuchBucket", http_status_code=404)
        with self.assertLogs("app.services.lesson_service", level="ERROR") as captured:
            response = await self.get()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "VIDEO_STORAGE_UNAVAILABLE")
        self.assertIn("aws_code=NoSuchBucket", captured.output[0])
        self.assertIn("operation=HeadObject", captured.output[0])
        self.assertNotIn("NoSuchBucket", response.text)

    async def test_missing_credentials(self):
        self.factory.side_effect = NoCredentialsError()
        with self.assertLogs("app.services.lesson_service", level="ERROR") as captured:
            response = await self.get()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "VIDEO_STORAGE_UNAVAILABLE")
        self.assertIn("exception_type=NoCredentialsError", captured.output[0])
        self.assertIn("operation=CreateS3Client", captured.output[0])
        self.assertNotIn("NoCredentialsError", response.text)

    async def test_network_error(self):
        self.factory.side_effect = EndpointConnectionError(endpoint_url="https://s3.invalid")
        self.assertEqual((await self.get()).status_code, 502)

    async def test_head_error_logs_context_without_aws_messages_or_credentials(self):
        secret = "DO_NOT_LOG_ACCESS_KEY_SECRET_OR_SIGNED_URL"
        self.stub.add_client_error(
            "head_object", service_error_code="ExpiredToken", service_message=secret,
            http_status_code=400, response_meta={"HTTPHeaders": {"Authorization": secret}},
        )
        with self.assertLogs("app", level="ERROR") as captured:
            response = await self.get()
        logs = "\n".join(captured.output)
        for expected in (
            "exception_type=ClientError", "aws_code=ExpiredToken", "aws_status=400",
            "operation=HeadObject", f"bucket={settings.S3_BUCKET}", "region=ap-southeast-1", "pid=",
        ):
            self.assertIn(expected, logs)
        self.assertNotIn(secret, logs)
        self.assertNotIn(secret, response.text)
        self.assertNotIn("ExpiredToken", response.text)
        self.assertEqual(response.status_code, 502)
        diagnostic = next(r for r in captured.records if r.name == "app.services.lesson_service")
        self.assertFalse(diagnostic.exc_info)
        self.assertIsNone(diagnostic.stack_info)

    async def test_presign_failure_is_distinguished_from_head_failure(self):
        self.head_ok()
        secret_url = "https://s3.invalid/video?X-Amz-Credential=SECRET&X-Amz-Signature=SECRET"
        with patch.object(self.s3, "generate_presigned_url", side_effect=EndpointConnectionError(endpoint_url=secret_url)):
            with self.assertLogs("app", level="ERROR") as captured:
                response = await self.get()
        logs = "\n".join(captured.output)
        self.assertIn("operation=GeneratePresignedGetUrl", logs)
        self.assertIn("exception_type=EndpointConnectionError", logs)
        self.assertNotIn("SECRET", logs)
        self.assertNotIn(secret_url, response.text)
        self.assertEqual(response.status_code, 502)

    async def test_profile_not_found_is_logged_without_changing_public_error(self):
        self.factory.side_effect = ProfileNotFound(profile="missing-profile")
        with self.assertLogs("app.services.lesson_service", level="ERROR") as captured:
            response = await self.get()
        self.assertIn("exception_type=ProfileNotFound", captured.output[0])
        self.assertEqual(response.json()["code"], "VIDEO_STORAGE_UNAVAILABLE")

    async def test_logs_session_profile_separately_from_process_environment(self):
        self.stub.add_client_error("head_object", service_error_code="ExpiredToken", http_status_code=400)
        with patch("app.adapters.storage.s3_storage.boto3.DEFAULT_SESSION", SimpleNamespace(profile_name="learncloud")):
            with patch.dict("os.environ", {"AWS_PROFILE": "different-process-profile"}):
                with self.assertLogs("app.services.lesson_service", level="ERROR") as captured:
                    response = await self.get()
        self.assertEqual(response.status_code, 502)
        self.assertIn("session_profile=learncloud", captured.output[0])
        self.assertIn("process_profile=different-process-profile", captured.output[0])

    async def test_ssl_error_does_not_log_exception_message_or_endpoint(self):
        secret_url = "https://s3.invalid/?X-Amz-Signature=DO_NOT_LOG"
        with patch.object(self.s3, "head_object", side_effect=SSLError(endpoint_url=secret_url, error="DO_NOT_LOG")):
            with self.assertLogs("app", level="ERROR") as captured:
                response = await self.get()
        logs = "\n".join(captured.output)
        self.assertIn("exception_type=SSLError", logs)
        self.assertIn("operation=HeadObject", logs)
        self.assertNotIn("DO_NOT_LOG", logs)
        self.assertNotIn("DO_NOT_LOG", response.text)
        self.assertEqual(response.status_code, 502)

    def test_presigned_put_still_signs_upload_without_head(self):
        from app.adapters.storage.s3_storage import S3StorageAdapter

        adapter = S3StorageAdapter()
        # No stubbed HEAD response: a new read/HEAD call would fail this test.
        with patch.object(self.s3, "generate_presigned_url", wraps=self.s3.generate_presigned_url) as sign:
            url = adapter.generate_upload_url(
                object_key="lessons/8/raw/upload-test.mp4", content_type="video/mp4"
            )
        sign.assert_called_once_with(
            ClientMethod="put_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": "lessons/8/raw/upload-test.mp4", "ContentType": "video/mp4"},
            ExpiresIn=900, HttpMethod="PUT",
        )
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
        self.assertIn("content-type", query["X-Amz-SignedHeaders"][0])
        self.assertEqual(query["X-Amz-Expires"], ["900"])
        self.assertEqual(unquote(urlsplit(url).path), "/lessons/8/raw/upload-test.mp4")

    async def test_upload_api_still_returns_sigv4_put(self):
        self.course.status = "DRAFT"
        self.lesson.status = "DRAFT"
        self.lesson.raw_video_key = None
        self.stub.add_response("list_objects_v2", {"IsTruncated": False}, {
            "Bucket": settings.S3_BUCKET,
            "Prefix": "lessons/8/raw/",
            "MaxKeys": 2,
        })
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/lessons/8/upload-url", json={
                "filename": "input.mp4", "content_type": "video/mp4", "file_size": 1024,
            })
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["method"], "PUT")
        self.assertEqual(payload["content_type"], "video/mp4")
        self.assertTrue(payload["object_key"].startswith("lessons/8/raw/"))
        self.assertEqual(parse_qs(urlsplit(payload["upload_url"]).query)["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
        self.db.query.assert_called()

    async def test_upload_api_still_requires_instructor(self):
        self.user.role = "STUDENT"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/lessons/8/upload-url", json={
                "filename": "input.mp4", "content_type": "video/mp4", "file_size": 1024,
            })
        self.assertEqual(response.status_code, 403)
        self.factory.assert_not_called()

    async def test_openapi_response_and_identity_dependency(self):
        response = await self.get("/openapi.json")
        operation = response.json()["paths"]["/lessons/{lesson_id}/video-url"]["get"]
        self.assertIn("200", operation["responses"])
        self.assertIn({"HTTPBearer": []}, operation["security"])
        schema = response.json()["components"]["schemas"]["LessonVideoUrlResponse"]
        self.assertEqual(set(schema["required"]), {"lesson_id", "video_url", "expires_in", "content_type"})

    def test_safe_configuration_defaults(self):
        with patch.dict("os.environ", {}, clear=True):
            defaults = Settings(_env_file=None, DATABASE_URL="postgresql://unused", JWT_SECRET_KEY="x" * 32)
        self.assertEqual(defaults.APP_ENV, "production")
        self.assertFalse(defaults.ALLOW_RAW_VIDEO_PLAYBACK)


class PlaybackConfigTests(unittest.TestCase):
    def test_project_dotenv_path_is_absolute_and_independent_of_working_directory(self):
        expected = Path(config.__file__).resolve().parents[2] / ".env"
        self.assertEqual(Settings.model_config["env_file"], expected)
        self.assertTrue(expected.is_absolute())

    def test_explicit_development_flags_are_loaded_from_dotenv(self):
        with TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            dotenv = Path(directory) / ".env"
            dotenv.write_text("APP_ENV=development\nALLOW_RAW_VIDEO_PLAYBACK=true\n", encoding="utf-8")
            loaded = Settings(_env_file=dotenv, DATABASE_URL="postgresql://unused", JWT_SECRET_KEY="x" * 32)
            self.assertEqual(loaded.APP_ENV, "development")
            self.assertTrue(loaded.ALLOW_RAW_VIDEO_PLAYBACK)

    def test_process_environment_overrides_dotenv(self):
        with TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"APP_ENV": "production", "ALLOW_RAW_VIDEO_PLAYBACK": "false"}, clear=True
        ):
            dotenv = Path(directory) / ".env"
            dotenv.write_text("APP_ENV=development\nALLOW_RAW_VIDEO_PLAYBACK=true\n", encoding="utf-8")
            loaded = Settings(_env_file=dotenv, DATABASE_URL="postgresql://unused", JWT_SECRET_KEY="x" * 32)
            self.assertEqual(loaded.APP_ENV, "production")
            self.assertFalse(loaded.ALLOW_RAW_VIDEO_PLAYBACK)


if __name__ == "__main__":
    unittest.main()
