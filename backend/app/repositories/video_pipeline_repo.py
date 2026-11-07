"""Transactions belong to services. Course/Lesson locks serialize pipeline writes.

Every run-to-upload read must match the composite upload_id/lesson_id identity.
Upload intents may coexist; the first validated claim wins under the Lesson lock.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.video_pipeline import VideoPipelineRun, VideoUpload


def get_upload(db: Session, key: str):
    return db.scalars(select(VideoUpload).where(VideoUpload.source_key == key)).first()


def get_run(db: Session, run_id: str):
    return db.get(VideoPipelineRun, run_id)


def upload_for_run(db: Session, run: VideoPipelineRun):
    return db.scalars(select(VideoUpload).where(
        VideoUpload.id == run.upload_id, VideoUpload.lesson_id == run.lesson_id,
    )).first()


def run_for_attempt(db: Session, upload_id: str, attempt: int):
    return db.scalars(select(VideoPipelineRun).where(
        VideoPipelineRun.upload_id == upload_id, VideoPipelineRun.attempt == attempt,
    )).first()


def run_for_execution(db: Session, execution_arn: str):
    return db.scalars(select(VideoPipelineRun).where(VideoPipelineRun.execution_arn == execution_arn)).first()


def pending_dispatches(db: Session, now):
    # Relay never takes lesson locks: it only advances delivery time, not job state.
    return db.scalars(select(VideoPipelineRun).where(
        VideoPipelineRun.state == "QUEUED", VideoPipelineRun.next_dispatch_at <= now,
    ).order_by(VideoPipelineRun.next_dispatch_at).limit(10).with_for_update(skip_locked=True)).all()
