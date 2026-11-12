"""Opt-in K5 test against only a local, explicitly named PostgreSQL database."""

import os
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz
from app.models.section import Section
from app.models.user import User
from app.models.video_pipeline import VideoPipelineRun, VideoUpload
from app.services import ai_worker_service, video_pipeline_service


def _isolated_url():
    value = os.environ.get("LEARNCLOUD_PIPELINE_TEST_DATABASE_URL", "")
    try:
        url = make_url(value)
    except Exception:
        raise RuntimeError("An explicit isolated PostgreSQL test URL is required.") from None
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg2"}
        or url.database != "learncloud_pipeline_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise RuntimeError("Only local database learncloud_pipeline_test is permitted.")
    return url


pytestmark = pytest.mark.skipif(
    os.environ.get("LEARNCLOUD_RUN_PIPELINE_DB_TESTS") != "1",
    reason="isolated PostgreSQL K5 tests are opt-in",
)


def test_k5_transaction_and_retry_idempotency_on_postgresql():
    engine = create_engine(_isolated_url(), connect_args={"connect_timeout": 3})
    stack = ExitStack()
    stack.callback(engine.dispose)
    stack.enter_context(patch("boto3.client", side_effect=AssertionError("AWS client forbidden")))
    stack.enter_context(patch("botocore.client.BaseClient._make_api_call", side_effect=AssertionError("AWS call forbidden")))
    connection = engine.connect()
    stack.callback(connection.close)
    outer = connection.begin()
    stack.callback(outer.rollback)
    db = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    stack.callback(db.close)
    try:
        assert connection.execute(text("SELECT current_database()" )).scalar_one() == "learncloud_pipeline_test"
        assert connection.execute(text(
            "SELECT count(*) FROM schema_migrations WHERE version='0005'"
        )).scalar_one() == 1

        suffix = uuid4().hex
        owner = f"arn:aws:states:ap-southeast-1:000000000000:execution:k5:{suffix}"
        instructor = User(name="K5 PG", email=f"k5-{suffix}@test.local", role="INSTRUCTOR")
        db.add(instructor)
        db.flush()
        course = Course(instructor_id=instructor.id, title="K5 PG", status="DRAFT")
        db.add(course)
        db.flush()
        section = Section(course_id=course.id, title="K5", position=1)
        db.add(section)
        db.flush()
        lesson = Lesson(section_id=section.id, title="K5", position=1, status="PROCESSING")
        db.add(lesson)
        db.flush()
        upload_id = uuid4().hex
        raw = f"lessons/{lesson.id}/raw/{upload_id}.mp4"
        output = f"lessons/{lesson.id}/processed/{upload_id}/attempt-1/video_720p.mp4"
        lesson.raw_video_key, lesson.processed_video_key = raw, output
        now = datetime.now(timezone.utc)
        upload = VideoUpload(
            id=upload_id, lesson_id=lesson.id, source_key=raw,
            content_type="video/mp4", size_bytes=100,
            created_at=now, expires_at=now + timedelta(minutes=15),
        )
        run_id = video_pipeline_service.run_identity(upload_id, 0)
        run = VideoPipelineRun(
            id=run_id, upload_id=upload_id, lesson_id=lesson.id, attempt=0,
            state="VIDEO_READY", execution_arn=owner, source_etag="e" * 32,
            output_key=output, safe_to_retry=True,
        )
        db.add(upload)
        db.flush()
        db.add(run)
        db.commit()

        job_id = ai_worker_service.transcription_job_name(run_id)
        transcriber, store, ai = Mock(), Mock(), Mock()
        transcriber.start_job.return_value = {"job_id": job_id, "status": "IN_PROGRESS"}
        transcriber.get_job_status.return_value = {"job_id": job_id, "status": "COMPLETED"}
        store.read.return_value = {"text": "PostgreSQL cloud transcript", "segments": []}
        ai.generate_summary.return_value = {"title": "Cloud", "summary": "Cloud summary"}
        ai.extract_key_concepts.return_value = [{"term": "Cloud", "definition": "Elastic resources"}]
        ai.generate_quiz.return_value = {"questions": [{
            "question": f"Question {i}?", "options": ["A", "B", "C", "D"],
            "correct_answer": "A", "explanation": "A is correct",
        } for i in range(1, 4)]}

        ai_worker_service.start_transcription(db, run_id, owner, transcriber)
        ai_worker_service.poll_transcription(db, run_id, owner, job_id, transcriber)
        proof = ai_worker_service.generate_content(
            db, run_id, owner, job_id,
            transcriber=transcriber, transcript_store=store, ai=ai,
        )
        assert ai_worker_service.generate_content(
            db, run_id, owner, job_id,
            transcriber=transcriber, transcript_store=store, ai=ai,
        ) == proof
        assert db.query(Quiz).filter_by(section_id=section.id).count() == 1
        assert db.query(Question).join(Quiz).filter(Quiz.section_id == section.id).count() == 3
        assert db.query(Flashcard).filter_by(lesson_id=lesson.id).count() == 1
        assert ai.generate_summary.call_count == 1
        video_pipeline_service.finalize_ai(db, run_id, owner, proof)
        assert lesson.status == "REVIEW_REQUIRED"
        assert run.state == "COMPLETE"
    finally:
        stack.close()
