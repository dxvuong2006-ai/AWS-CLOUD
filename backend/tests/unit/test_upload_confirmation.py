"""Real database/JWT/guards and a fake S3 object store; no network/AWS writes."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from botocore.exceptions import ClientError
import pytest

from test_lesson_video_status import video_http
from app.api import uploads
from app.config import settings
from app.models.video_pipeline import VideoUpload, VideoPipelineRun
from app.services.upload_service import UploadService
from app.services import processing_service, video_pipeline_service as pipeline
from app.adapters.video.base import ProcessingReceipt


@pytest.fixture
def upload_http(video_http,monkeypatch):
    h=video_http
    h.client.app.include_router(uploads.router)
    monkeypatch.setattr(settings,"VIDEO_PIPELINE_ENABLED",False)
    objects={}
    storage=Mock()
    storage.has_raw_video_objects.side_effect=lambda lesson_id:any(key.startswith(f"lessons/{lesson_id}/raw/") for key in objects)
    storage.generate_upload_url.return_value="https://s3.example.test/conditional-put"
    def head(key):
        if key not in objects:
            raise ClientError({"Error":{"Code":"NoSuchKey"}},"HeadObject")
        return objects[key]
    storage.head_video.side_effect=head
    monkeypatch.setattr(uploads,"S3StorageAdapter",lambda:storage)
    def put(intent,**changes):
        objects[intent["object_key"]]={"ContentLength":100,"ContentType":"video/mp4",
            "ETag":'"'+"a"*32+'"',"LastModified":datetime.now(timezone.utc),**changes}
    h.storage,h.objects,h.put=storage,objects,put
    yield h


def reserve(h,**changes):
    return h.client.post("/lessons/1/upload-url",headers=h.headers(),json={
        "filename":"video.mp4","content_type":"video/mp4","file_size":100,**changes})


def confirm(h,intent,uid=1,lesson_id=1):
    return h.client.post(f"/lessons/{lesson_id}/confirm-upload",headers=h.headers(uid),json={"upload_id":intent["upload_id"]})


def test_first_upload_is_durable_and_confirmed_before_attachment(upload_http):
    h=upload_http
    result=reserve(h)
    assert result.status_code==200
    intent=result.json()
    assert h.db.query(VideoUpload).count()==1
    assert h.db.get(VideoUpload,intent["upload_id"]).lesson_id==1
    assert h.db.get(VideoUpload,intent["upload_id"]).source_key==intent["object_key"]
    assert h.lesson.raw_video_key is None and h.lesson.status=="DRAFT"
    assert intent["required_headers"]["If-None-Match"]=="*"
    h.storage.generate_upload_url.assert_called_once_with(object_key=intent["object_key"],content_type="video/mp4",prevent_overwrite=True)
    pending=h.client.get("/instructor/courses/1",headers=h.headers()).json()["sections"][0]["lessons"][0]
    assert pending["video_status"]=="UPLOAD_PENDING" and pending["pending_upload_id"]==intent["upload_id"]
    assert confirm(h,intent).status_code==404
    assert h.lesson.raw_video_key is None
    h.put(intent)
    result=confirm(h,intent)
    assert result.status_code==200 and result.json()["video_status"]=="UPLOADED"
    assert h.lesson.raw_video_key==intent["object_key"] and h.lesson.status=="UPLOADED"
    assert confirm(h,intent).status_code==200
    assert h.db.query(VideoUpload).count()==1 and h.db.query(VideoPipelineRun).count()==0
    assert reserve(h).status_code==409
    for path in ("/sections/1/lessons","/lessons/1","/lessons/1/processing-status","/courses/instructor/me","/instructor/courses/1"):
        response=h.client.get(path,headers=h.headers())
        assert response.status_code==200
        assert '"video_status":"UPLOADED"' in response.text
        assert '"upload_pending":true' not in response.text
    h.aws.assert_not_called()


def test_repeat_and_failed_transfer_resume_the_same_key(upload_http):
    h=upload_http
    first=reserve(h).json()
    second=reserve(h).json()
    assert (first["upload_id"],first["object_key"])==(second["upload_id"],second["object_key"])
    assert h.db.query(VideoUpload).count()==1
    assert reserve(h,file_size=101).status_code==409
    upload=h.db.get(VideoUpload,first["upload_id"])
    upload.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)
    h.db.commit()
    resumed=reserve(h).json()
    assert resumed["object_key"]==first["object_key"]
    h.put(resumed)
    assert confirm(h,resumed).status_code==200


@pytest.mark.parametrize("changes",[{"ContentLength":101},{"ContentType":"text/plain"},{"ETag":""},
    {"LastModified":datetime(2000,1,1,tzinfo=timezone.utc)}])
def test_confirmation_checks_s3_metadata_without_attaching_bad_file(upload_http,changes):
    h=upload_http
    intent=reserve(h).json()
    h.put(intent,**changes)
    assert confirm(h,intent).status_code==409
    h.db.refresh(h.lesson)
    assert h.lesson.raw_video_key is None and h.lesson.status=="DRAFT"


@pytest.mark.parametrize("state",["UPLOADED","PROCESSING","TRANSCRIBING","AI_PROCESSING","REVIEW_REQUIRED","PUBLISHED","FAILED"])
def test_existing_or_processing_video_never_gets_a_fresh_upload(upload_http,state):
    h=upload_http
    h.lesson.status=state; h.lesson.raw_video_key="original/raw.mp4"
    h.db.commit()
    assert reserve(h).status_code==409
    assert h.db.query(VideoUpload).count()==0
    assert h.lesson.raw_video_key=="original/raw.mp4"


@pytest.mark.parametrize("event_first",[False,True])
def test_confirmation_and_eventbridge_claim_do_not_regress_or_duplicate(upload_http,monkeypatch,event_first):
    h=upload_http
    monkeypatch.setattr(settings,"VIDEO_PIPELINE_ENABLED",True)
    intent=reserve(h).json(); h.put(intent)
    # PostgreSQL returns timezone-aware TIMESTAMPTZ. SQLite strips timezone
    # information; match the real pipeline DB contract in this unit fixture.
    h.db.expire_on_commit=False
    upload=h.db.get(VideoUpload,intent["upload_id"])
    upload.created_at=upload.created_at.replace(tzinfo=timezone.utc)
    upload.expires_at=upload.expires_at.replace(tzinfo=timezone.utc)
    payload={"kind":"upload","bucket":settings.S3_BUCKET,"key":intent["object_key"],"etag":"a"*32}
    if event_first:
        pipeline.claim(h.db,payload,"unit-execution",h.storage)
    else:
        assert confirm(h,intent).json()["status"]=="DRAFT"
        assert h.lesson.raw_video_key==intent["object_key"]
        assert h.db.query(VideoPipelineRun).count()==0
    pipeline.claim(h.db,payload,"unit-execution",h.storage)
    assert confirm(h,intent).json()["status"]=="PROCESSING"
    assert h.db.query(VideoPipelineRun).count()==1
    assert h.lesson.raw_video_key==intent["object_key"]


def test_processing_retry_reuses_current_raw_and_never_creates_an_upload(upload_http,monkeypatch):
    h=upload_http
    intent=reserve(h).json(); h.put(intent); confirm(h,intent)
    h.lesson.status="FAILED"; h.db.commit()
    monkeypatch.setattr(processing_service,"S3StorageAdapter",lambda:h.storage)
    processor=SimpleNamespace(start=lambda req:ProcessingReceipt(req.job_id))
    monkeypatch.setattr(processing_service,"get_video_processor",lambda db:processor)
    response=h.client.post("/lessons/1/retry",headers=h.headers())
    assert response.status_code==202 and response.json()["status"]=="PROCESSING"
    assert h.lesson.raw_video_key==intent["object_key"] and h.lesson.retry_count==1
    assert h.db.query(VideoUpload).count()==1
    assert reserve(h).status_code==409


def test_owner_role_and_server_issued_identity_are_required(upload_http):
    h=upload_http
    intent=reserve(h).json(); h.put(intent)
    for uid in (2,3):
        assert confirm(h,intent,uid=uid).status_code in {403,404}
        assert h.client.post("/lessons/1/upload-url",headers=h.headers(uid),json={"filename":"v.mp4","content_type":"video/mp4","file_size":100}).status_code in {403,404}
    assert h.client.post("/lessons/1/confirm-upload",json={"upload_id":intent["upload_id"]}).status_code==401
    assert confirm(h,{"upload_id":"f"*32}).status_code==404
    assert h.client.post("/lessons/1/confirm-upload",headers=h.headers(),json={"upload_id":intent["upload_id"],"object_key":"attacker.mp4"}).status_code==422
    assert h.lesson.raw_video_key is None


def test_failed_signer_rolls_back_reservation(upload_http):
    h=upload_http
    h.storage.generate_upload_url.side_effect=RuntimeError("signer failure")
    with pytest.raises(RuntimeError): reserve(h)
    assert h.db.query(VideoUpload).count()==0 and h.lesson.raw_video_key is None


def test_late_event_cannot_replace_another_current_video(upload_http,monkeypatch):
    h=upload_http
    monkeypatch.setattr(settings,"VIDEO_PIPELINE_ENABLED",True)
    intent=reserve(h).json(); h.put(intent)
    h.lesson.raw_video_key="existing/raw.mp4"; h.lesson.processed_video_key="existing/processed.mp4"
    h.lesson.summary="Preserve existing lesson content"; h.db.commit()
    payload={"kind":"upload","bucket":settings.S3_BUCKET,"key":intent["object_key"],"etag":"a"*32}
    assert pipeline.claim(h.db,payload,"late-execution",h.storage)=={"decision":"IGNORE"}
    assert h.lesson.raw_video_key=="existing/raw.mp4" and h.lesson.processed_video_key=="existing/processed.mp4"
    assert h.lesson.summary=="Preserve existing lesson content"
    assert confirm(h,intent).status_code==409
    assert h.db.query(VideoPipelineRun).count()==0


def test_malformed_or_cross_lesson_ledger_key_is_never_confirmed(upload_http):
    h=upload_http
    intent=reserve(h).json()
    row=h.db.get(VideoUpload,intent["upload_id"])
    row.source_key=f"lessons/999/raw/{row.id}.mp4"
    h.db.commit()
    assert confirm(h,intent).status_code==409
    assert reserve(h).status_code==409
    h.storage.head_video.assert_not_called()


def test_unlinked_legacy_raw_and_inventory_denial_never_issue_a_second_key(upload_http):
    h=upload_http
    h.objects["lessons/1/raw/old-unlinked.mp4"]={"ContentLength":100}
    response=reserve(h)
    assert response.status_code==409 and response.json()["code"]=="UNLINKED_RAW_VIDEO"
    h.storage.generate_upload_url.assert_not_called()
    assert h.db.query(VideoUpload).count()==0 and h.lesson.raw_video_key is None
    h.storage.has_raw_video_objects.side_effect=ClientError({"Error":{"Code":"AccessDenied"}},"ListObjectsV2")
    response=reserve(h)
    assert response.status_code==502 and response.json()["code"]=="UPLOAD_INVENTORY_UNAVAILABLE"
    h.storage.generate_upload_url.assert_not_called()


def test_s3_inventory_is_limited_to_this_lesson_and_never_writes():
    from app.adapters.storage.s3_storage import S3StorageAdapter
    adapter=S3StorageAdapter.__new__(S3StorageAdapter)
    adapter.bucket="unit-bucket"
    adapter.client=Mock()
    adapter.client.list_objects_v2.return_value={"Contents":[{"Key":"lessons/42/raw/"}]}
    assert adapter.has_raw_video_objects(42) is False
    adapter.client.list_objects_v2.assert_called_once_with(Bucket="unit-bucket",Prefix="lessons/42/raw/",MaxKeys=2)
    adapter.client.list_objects_v2.return_value={"Contents":[{"Key":"lessons/42/raw/existing.mp4"}]}
    assert adapter.has_raw_video_objects(42) is True
    adapter.client.list_objects_v2.return_value={"IsTruncated":True}
    assert adapter.has_raw_video_objects(42) is True
    adapter.client.put_object.assert_not_called()
    adapter.client.delete_object.assert_not_called()
