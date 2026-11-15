"""Concurrent upload reservation on an explicitly isolated local PostgreSQL DB.

All S3 operations are in-memory doubles. Never uses application DATABASE_URL.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.course import Course
from app.models.section import Section
from app.models.lesson import Lesson
from app.models.video_pipeline import VideoUpload, VideoPipelineRun
from app.services.upload_service import UploadService
from app.utils.errors import ConflictError


RUN = os.environ.get("LEARNCLOUD_RUN_UPLOAD_DB_TESTS") == "1"


def isolated_upload_test_url(value):
    url=make_url(value)
    if (url.get_backend_name()!="postgresql" or url.host not in {"127.0.0.1","localhost","::1"}
        or url.database!="learncloud_auth_test" or url.username!="learncloud_auth_test"
        or not set(url.query).issubset({"connect_timeout","application_name"})):
        raise RuntimeError("Only isolated local learncloud_auth_test DB/user is allowed")
    return url


@pytest.fixture
def pg_upload():
    if not RUN: pytest.skip("Explicit isolated PostgreSQL upload tests are opt-in")
    engine=create_engine(isolated_upload_test_url(os.environ["LEARNCLOUD_UPLOAD_TEST_DATABASE_URL"]),hide_parameters=True)
    ids={}
    try:
        with engine.connect() as c:
            assert c.scalar(text("SELECT current_database()"))=="learncloud_auth_test"
            assert c.scalar(text("SELECT to_regclass('public.video_uploads') IS NOT NULL"))
        with Session(engine,expire_on_commit=False) as db:
            user=User(name="Upload test",email=f"upload-{uuid4().hex}@example.com",role="INSTRUCTOR",cognito_sub=uuid4().hex)
            db.add(user); db.flush(); ids["user"]=user.id
            course=Course(title="Isolated upload course",instructor_id=user.id)
            db.add(course); db.flush(); ids["course"]=course.id
            section=Section(title="Section",position=1,course_id=course.id)
            db.add(section); db.flush(); ids["section"]=section.id
            lesson=Lesson(title="Upload concurrency test",position=1,section_id=section.id)
            db.add(lesson); db.flush(); ids["lesson"]=lesson.id
            db.commit()
        yield engine,ids
    finally:
        # Only this test's IDs in the strictly validated isolated database.
        if "lesson" in ids:
            with engine.begin() as c:
                c.execute(delete(VideoPipelineRun).where(VideoPipelineRun.lesson_id==ids["lesson"]))
                c.execute(delete(VideoUpload).where(VideoUpload.lesson_id==ids["lesson"]))
                c.execute(delete(Lesson).where(Lesson.id==ids["lesson"]))
                c.execute(delete(Section).where(Section.id==ids["section"]))
                c.execute(delete(Course).where(Course.id==ids["course"]))
                c.execute(delete(User).where(User.id==ids["user"]))
        engine.dispose()


def test_concurrent_requests_reserve_one_immutable_key(pg_upload):
    engine,ids=pg_upload
    holding,release=Event(),Event()
    def slow_signer(**kwargs):
        assert kwargs["prevent_overwrite"] is True
        holding.set()
        assert release.wait(5)
        return "https://s3.example.test/put"
    slow=SimpleNamespace(generate_upload_url=slow_signer,has_raw_video_objects=lambda lesson_id:False)
    fast=SimpleNamespace(generate_upload_url=lambda **kwargs:"https://s3.example.test/put",has_raw_video_objects=lambda lesson_id:False)
    def reserve(storage):
        with Session(engine) as db:
            return UploadService(storage).create_upload_url(db,ids["lesson"],ids["user"],"video.mp4","video/mp4",100)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(reserve,slow)
        assert holding.wait(5)
        second=pool.submit(reserve,fast)
        try:
            with pytest.raises(ConflictError) as exc: second.result(timeout=5)
            assert exc.value.code=="UPLOAD_BUSY"
        finally:
            release.set()
        intent=first.result(timeout=5)
    resumed=reserve(fast)
    assert resumed["upload_id"]==intent["upload_id"] and resumed["object_key"]==intent["object_key"]
    with Session(engine) as db:
        assert db.query(VideoUpload).filter_by(lesson_id=ids["lesson"]).count()==1
        lesson=db.get(Lesson,ids["lesson"])
        assert lesson.raw_video_key is None and lesson.status=="DRAFT"


def test_confirmation_persists_exact_raw_and_blocks_fresh_upload(pg_upload,monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings,"VIDEO_PIPELINE_ENABLED",False)
    engine,ids=pg_upload
    metadata={"ContentLength":100,"ContentType":"video/mp4","ETag":'"'+"a"*32+'"',"LastModified":datetime.now(timezone.utc)}
    storage=SimpleNamespace(generate_upload_url=lambda **kw:"https://s3.example.test/put",head_video=lambda key:metadata,
                            has_raw_video_objects=lambda lesson_id:False)
    with Session(engine) as db:
        service=UploadService(storage)
        intent=service.create_upload_url(db,ids["lesson"],ids["user"],"video.mp4","video/mp4",100)
        metadata["LastModified"]=datetime.now(timezone.utc)
        result=service.confirm_upload(db,ids["lesson"],ids["user"],intent["upload_id"])
        assert result["status"]=="UPLOADED" and result["video_status"]=="UPLOADED"
    with Session(engine) as db:
        lesson=db.get(Lesson,ids["lesson"])
        assert lesson.raw_video_key==intent["object_key"] and lesson.status=="UPLOADED"
        with pytest.raises(ConflictError):
            UploadService(storage).create_upload_url(db,ids["lesson"],ids["user"],"other.mp4","video/mp4",100)


@pytest.mark.parametrize("value",[
    "postgresql://learncloud_admin@127.0.0.1:15437/learncloud",
    "postgresql://user@production.example.com/learncloud",
    "postgresql://learncloud_auth_test@127.0.0.1/learncloud_auth_test?host=production.example.com",
])
def test_refuse_application_rds_and_tunnel_targets(value):
    with pytest.raises(RuntimeError): isolated_upload_test_url(value)


def test_legacy_raw_recovery_cli_is_preview_first_and_one_time(pg_upload,monkeypatch,capsys):
    from scripts import attach_existing_raw_video as recovery
    from app.config import settings
    from app.adapters import storage
    from app.adapters.storage import s3_storage
    from unittest.mock import Mock
    engine,ids=pg_upload
    with engine.begin() as c:
        c.execute(text("""DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='learncloud_video_metadata_operator')
          THEN CREATE ROLE learncloud_video_metadata_operator NOLOGIN; END IF; END $$"""))
    import os
    url=isolated_upload_test_url(os.environ['LEARNCLOUD_UPLOAD_TEST_DATABASE_URL'])
    monkeypatch.setattr(settings,'DATABASE_URL',url.render_as_string(hide_password=False))
    monkeypatch.setattr(settings,'VIDEO_PIPELINE_ENABLED',False)
    monkeypatch.setattr(recovery.sys.stdin,'isatty',lambda:True)
    monkeypatch.setattr(recovery.getpass, 'getpass', lambda *args: url.password)
    key=f"lessons/{ids['lesson']}/raw/{uuid4().hex}.mp4"
    meta={'ContentLength':100,'ContentType':'video/mp4','ETag':'"'+'b'*32+'"',
          'LastModified':datetime(2020,1,1,tzinfo=timezone.utc)}
    fake=SimpleNamespace(head_video=lambda source:meta,
        generate_upload_url=Mock(side_effect=AssertionError('Recovery must never upload again')))
    monkeypatch.setattr(s3_storage,'S3StorageAdapter',lambda:fake)
    args=['--lesson-id',str(ids['lesson']),'--expected-instructor-id',str(ids['user']),
          '--object-key',key,'--operator-db-user','learncloud_auth_test','--approval-reference','TEST-RECOVERY']
    assert recovery.main(args)==0
    with Session(engine) as db:
        assert db.get(Lesson,ids['lesson']).raw_video_key is None
        assert db.query(VideoUpload).filter_by(lesson_id=ids['lesson']).count()==0
    monkeypatch.setattr('builtins.input',lambda *args:'WRONG')
    assert recovery.main(args+['--apply'])==1
    monkeypatch.setattr('builtins.input',lambda *args:f"ATTACH {ids['lesson']}")
    assert recovery.main(args+['--apply'])==0
    assert recovery.main(args+['--apply'])==1
    with Session(engine) as db:
        lesson=db.get(Lesson,ids['lesson'])
        assert lesson.raw_video_key==key and lesson.status=='UPLOADED'
        assert lesson.title=='Upload concurrency test' and lesson.section_id==ids['section']
        assert db.query(VideoUpload).filter_by(lesson_id=ids['lesson']).count()==1
    fake.generate_upload_url.assert_not_called()
    out=capsys.readouterr()
    assert key not in out.out+out.err
