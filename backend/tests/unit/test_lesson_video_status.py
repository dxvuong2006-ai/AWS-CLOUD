"""Actual HTTP serializers/owner guards against SQLite, with signed Cognito JWT.

No AWS calls, presigned URLs, RDS writes, migrations or pipeline transitions.
"""
from types import SimpleNamespace
from unittest.mock import Mock

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
import jwt
import pytest

from app.api import courses, lessons, screen_workflows
from app.config import settings
from app.dependencies import get_db
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.section import Section
from app.models.user import User
from app.schemas.lesson import LessonVideoFields
from app.utils.errors import register_exception_handlers


CASES = [
    ("DRAFT", None, None, "NOT_UPLOADED"),
    ("DRAFT", "raw/input.mp4", None, "UPLOADED"),
    ("DRAFT", "raw/input.mp4", "processed/video.mp4", "READY"),
    ("UPLOADED", "raw/input.mp4", None, "UPLOADED"),
    ("PROCESSING", "raw/input.mp4", None, "PROCESSING"),
    ("PROCESSING", "raw/input.mp4", "processed/video.mp4", "PROCESSING"),
    ("TRANSCRIBING", "raw/input.mp4", "processed/video.mp4", "PROCESSING"),
    ("AI_PROCESSING", "raw/input.mp4", "processed/video.mp4", "PROCESSING"),
    ("REVIEW_REQUIRED", "raw/input.mp4", "processed/video.mp4", "READY"),
    ("PUBLISHED", "raw/input.mp4", "processed/video.mp4", "READY"),
    ("PUBLISHED", "raw/input.mp4", None, "READY"),
    ("FAILED", "raw/input.mp4", "processed/video.mp4", "FAILED"),
]


@pytest.fixture
def video_http(db_session, monkeypatch):
    db = db_session
    for uid, role in ((1,"INSTRUCTOR"),(2,"INSTRUCTOR"),(3,"STUDENT")):
        db.add(User(id=uid, name=role, email=f"user{uid}@example.com", cognito_sub=f"video-user-{uid}", role=role))
    db.flush()
    db.add(Course(id=1, instructor_id=1, title="Course"))
    db.flush()
    db.add(Section(id=1, course_id=1, title="Section", position=1))
    db.flush()
    lesson = Lesson(id=1, section_id=1, title="Video lesson", position=1)
    db.add(lesson)
    db.commit()
    monkeypatch.setattr(settings,"COGNITO_REGION","ap-southeast-1")
    monkeypatch.setattr(settings,"COGNITO_USER_POOL_ID","ap-southeast-1_testpool")
    monkeypatch.setattr(settings,"COGNITO_APP_CLIENT_ID","test-client")
    key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
    monkeypatch.setattr(jwt,"PyJWKClient",lambda *a,**kw: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())))
    forbidden = Mock(side_effect=AssertionError("Video metadata reads must not call AWS"))
    monkeypatch.setattr("boto3.client",forbidden)
    app = FastAPI()
    register_exception_handlers(app)
    for router in (screen_workflows.router,lessons.router,courses.router):
        app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    def headers(uid=1):
        import time
        token=jwt.encode({"sub":f"video-user-{uid}","token_use":"access","client_id":"test-client",
            "iss":"https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_testpool",
            "exp":int(time.time())+300},key,algorithm="RS256")
        return {"Authorization":f"Bearer {token}"}
    with TestClient(app) as client:
        yield SimpleNamespace(client=client,db=db,lesson=lesson,headers=headers,aws=forbidden)


@pytest.mark.parametrize("status,raw,processed,expected",CASES)
def test_list_detail_and_processing_agree_without_pipeline_changes(video_http,status,raw,processed,expected):
    h=video_http
    h.lesson.status,h.lesson.raw_video_key,h.lesson.processed_video_key=status,raw,processed
    h.db.commit()
    before={c.name:getattr(h.lesson,c.name) for c in Lesson.__table__.columns}
    endpoints={
        "/instructor/courses/1": lambda body:body["sections"][0]["lessons"][0],
        "/instructor/courses": lambda body:body[0]["sections"][0]["lessons"][0],
        "/courses/instructor/me": lambda body:body[0]["sections"][0]["lessons"][0],
        "/sections/1/lessons": lambda body:body[0],
        "/lessons/1": lambda body:body,
        "/lessons/1/processing-status": lambda body:body,
    }
    for path,select in endpoints.items():
        response=h.client.get(path,headers=h.headers())
        assert response.status_code==200
        body=select(response.json())
        assert body["status"]==status
        assert body["video_status"]==expected
        assert body["has_raw_video"]==bool(raw)
        assert body["has_processed_video"]==bool(processed)
        assert "raw_video_key" not in body and "processed_video_key" not in body
        assert "video_url" not in body
        if path!="/lessons/1/processing-status":
            assert "error_message" not in body
        if raw: assert raw not in response.text
        if processed: assert processed not in response.text
        if path.startswith("/instructor/") or path.endswith("processing-status"):
            assert response.headers["cache-control"]=="no-store"
    h.db.refresh(h.lesson)
    assert {c.name:getattr(h.lesson,c.name) for c in Lesson.__table__.columns}==before
    h.aws.assert_not_called()


def test_unknown_missing_and_blank_metadata_never_default_to_draft():
    assert LessonVideoFields.model_validate({}).video_status=="UNKNOWN"
    assert LessonVideoFields.model_validate({"status":"FUTURE_STATE"}).video_status=="UNKNOWN"
    model=LessonVideoFields.model_validate({"status":"DRAFT","raw_video_key":"  ","processed_video_key":""})
    assert model.video_status=="NOT_UPLOADED" and not model.has_raw_video


@pytest.mark.parametrize("uid",[2,3])
def test_instructor_metadata_remains_owner_scoped(video_http,uid):
    h=video_http
    for path in ("/instructor/courses/1","/lessons/1/processing-status","/sections/1/lessons","/lessons/1"):
        assert h.client.get(path,headers=h.headers(uid)).status_code in {403,404}
    assert h.client.get("/instructor/courses/1").status_code==401


def test_refresh_reads_current_status_after_upload_and_completion(video_http):
    h=video_http
    def row():
        return h.client.get("/instructor/courses/1",headers=h.headers()).json()["sections"][0]["lessons"][0]
    assert row()["video_status"]=="NOT_UPLOADED"
    h.lesson.raw_video_key="raw/input.mp4"
    h.lesson.status="PROCESSING"
    h.db.commit()
    assert row()["video_status"]=="PROCESSING"
    h.lesson.processed_video_key="processed/video.mp4"
    h.lesson.status="REVIEW_REQUIRED"
    h.db.commit()
    assert row()["video_status"]=="READY"
