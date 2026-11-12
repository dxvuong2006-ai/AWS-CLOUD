"""K5 worker tests use injected AWS doubles and an isolated SQLite database."""

import importlib.util
import io
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from app.adapters.transcription.aws_transcribe import AWSTranscribeAdapter
from app.adapters.transcription.s3_transcript import S3TranscriptAdapter, parse_transcript
from app.config import settings
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.lesson import Lesson
from app.models.quiz import Question, Quiz
from app.models.section import Section
from app.models.user import User
from app.models.video_pipeline import VideoPipelineRun, VideoUpload
from app.services import ai_worker_service, video_pipeline_service


RUN_ID = "a" * 64
OWNER = "arn:aws:states:ap-southeast-1:000000000000:execution:k5:test"
UPLOAD_ID = "b" * 32
ROOT = Path(__file__).resolve().parents[3]


def _question(position):
    options = [f"A{position}", f"B{position}", f"C{position}", f"D{position}"]
    return {
        "question": f"Question {position}?", "options": options,
        "correct_answer": options[0], "explanation": "Because it is correct.",
    }


@pytest.fixture
def worker_context(db_session):
    instructor = User(name="K5 Owner", email="k5-owner@test.local", role="INSTRUCTOR")
    db_session.add(instructor)
    db_session.flush()
    course = Course(instructor_id=instructor.id, title="K5", status="DRAFT")
    db_session.add(course)
    db_session.flush()
    section = Section(course_id=course.id, title="AI", position=1)
    db_session.add(section)
    db_session.flush()
    lesson = Lesson(
        section_id=section.id, title="Pending AI", position=1,
        status="PROCESSING", retry_count=0,
        raw_video_key=f"lessons/1/raw/{UPLOAD_ID}.mp4",
        processed_video_key=f"lessons/1/processed/{UPLOAD_ID}/attempt-1/video_720p.mp4",
    )
    db_session.add(lesson)
    db_session.flush()
    lesson.raw_video_key = f"lessons/{lesson.id}/raw/{UPLOAD_ID}.mp4"
    lesson.processed_video_key = (
        f"lessons/{lesson.id}/processed/{UPLOAD_ID}/attempt-1/video_720p.mp4"
    )
    now = datetime.now(timezone.utc)
    upload = VideoUpload(
        id=UPLOAD_ID, lesson_id=lesson.id, source_key=lesson.raw_video_key,
        content_type="video/mp4", size_bytes=100, created_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    run = VideoPipelineRun(
        id=RUN_ID, upload_id=UPLOAD_ID, lesson_id=lesson.id, attempt=0,
        state="VIDEO_READY", execution_arn=OWNER, source_etag="e" * 32,
        output_key=lesson.processed_video_key, safe_to_retry=True,
    )
    db_session.add_all([upload, run])
    db_session.commit()
    return lesson, run


def _aws_doubles():
    transcriber = Mock()
    transcriber.start_job.return_value = {
        "job_id": f"learncloud-k5-{RUN_ID}", "status": "IN_PROGRESS", "source": "aws",
    }
    transcriber.get_job_status.return_value = {
        "job_id": f"learncloud-k5-{RUN_ID}", "status": "COMPLETED", "source": "aws",
    }
    store = Mock()
    store.read.return_value = {
        "text": "Cloud computing provides elastic infrastructure.",
        "segments": [{"start": 0.0, "end": 1.0, "text": "Cloud"}],
    }
    ai = Mock()
    ai.generate_summary.return_value = {
        "title": "Cloud computing", "summary": "A concise cloud summary.",
        "key_concepts": [
            {"term": "Elasticity", "definition": "Resources scale with demand."},
            {"term": "IaaS", "definition": "Infrastructure delivered as a service."},
        ],
    }
    ai.generate_quiz.return_value = {"questions": [_question(i) for i in range(1, 4)]}
    return transcriber, store, ai


def test_start_poll_generate_and_finalize_are_idempotent(db_session, worker_context):
    lesson, run = worker_context
    transcriber, store, ai = _aws_doubles()
    with patch.object(settings, "TRANSCRIBE_OUTPUT_BUCKET", "learncloud-videos-mentorcloud"):
        started = ai_worker_service.start_transcription(
            db_session, RUN_ID, OWNER, transcriber,
        )
        assert started["status"] == "IN_PROGRESS"
        assert lesson.status == "TRANSCRIBING"
        assert transcriber.start_job.call_args.kwargs["allow_fallback"] is False

        polled = ai_worker_service.poll_transcription(
            db_session, RUN_ID, OWNER, started["job_id"], transcriber,
        )
        assert polled["status"] == "COMPLETED"
        assert lesson.status == "AI_PROCESSING"

        proof = ai_worker_service.generate_content(
            db_session, RUN_ID, OWNER, started["job_id"],
            transcriber=transcriber, transcript_store=store, ai=ai,
        )
        repeated = ai_worker_service.generate_content(
            db_session, RUN_ID, OWNER, started["job_id"],
            transcriber=transcriber, transcript_store=store, ai=ai,
        )

    assert repeated == proof == {"completed": True, "run_id": RUN_ID}
    assert ai.generate_summary.call_count == 1
    assert db_session.query(Quiz).count() == 1
    assert db_session.query(Question).count() == 3
    assert db_session.query(Flashcard).count() == 2
    assert lesson.status == "AI_PROCESSING"
    assert lesson.transcript_json["run_id"] == RUN_ID

    assert video_pipeline_service.finalize_ai(db_session, RUN_ID, OWNER, proof) == {
        "status": "REVIEW_REQUIRED",
    }
    assert lesson.status == "REVIEW_REQUIRED"
    assert run.state == "COMPLETE"


def test_stale_execution_is_rejected_before_aws(db_session, worker_context):
    transcriber, _, _ = _aws_doubles()
    with pytest.raises(ai_worker_service.AIWorkerError, match="STALE_EXECUTION"):
        ai_worker_service.start_transcription(
            db_session, RUN_ID, OWNER + ":other", transcriber,
        )
    transcriber.start_job.assert_not_called()


def test_transcribe_conflict_reuses_matching_deterministic_job():
    client = Mock()
    client.start_transcription_job.side_effect = ClientError(
        {"Error": {"Code": "ConflictException"}, "ResponseMetadata": {"HTTPStatusCode": 400}},
        "StartTranscriptionJob",
    )
    client.get_transcription_job.return_value = {"TranscriptionJob": {
        "TranscriptionJobName": f"learncloud-k5-{RUN_ID}",
        "TranscriptionJobStatus": "IN_PROGRESS",
        "LanguageCode": "vi-VN",
        "Media": {"MediaFileUri": "s3://bucket/video.mp4"},
    }}
    result = AWSTranscribeAdapter(client).start_job(
        "s3://bucket/video.mp4", job_name=f"learncloud-k5-{RUN_ID}",
        output_bucket="bucket", output_key="ai/transcript.json",
    )
    assert result["status"] == "IN_PROGRESS"
    client.get_transcription_job.assert_called_once()


def test_transcribe_conflict_rejects_mismatched_job_identity():
    client = Mock()
    client.start_transcription_job.side_effect = ClientError(
        {"Error": {"Code": "ConflictException"}, "ResponseMetadata": {"HTTPStatusCode": 400}},
        "StartTranscriptionJob",
    )
    client.get_transcription_job.return_value = {"TranscriptionJob": {
        "TranscriptionJobName": f"learncloud-k5-{RUN_ID}",
        "TranscriptionJobStatus": "IN_PROGRESS",
        "LanguageCode": "en-US",
        "Media": {"MediaFileUri": "s3://bucket/video.mp4"},
    }}
    with pytest.raises(ValueError, match="does not match"):
        AWSTranscribeAdapter(client).start_job(
            "s3://bucket/video.mp4", job_name=f"learncloud-k5-{RUN_ID}",
            output_bucket="bucket", output_key="ai/transcript.json",
        )


def test_oversized_transcript_is_rejected_before_bedrock(
    db_session, worker_context,
):
    transcriber, store, ai = _aws_doubles()
    store.read.return_value = {
        "text": "x" * 1_001,
        "segments": [],
    }
    with (
        patch.object(settings, "AI_TRANSCRIPT_MAX_CHARACTERS", 1_000),
        pytest.raises(ai_worker_service.AIWorkerError, match="INVALID_TRANSCRIPT_CONTENT"),
    ):
        ai_worker_service.generate_content(
            db_session, RUN_ID, OWNER, f"learncloud-k5-{RUN_ID}",
            transcriber=transcriber, transcript_store=store, ai=ai,
        )
    ai.generate_summary.assert_not_called()
    ai.generate_quiz.assert_not_called()


def test_parse_realistic_transcribe_result():
    result = parse_transcript({
        "status": "COMPLETED",
        "results": {
            "transcripts": [{"transcript": "Xin chao cloud."}],
            "items": [{
                "type": "pronunciation", "start_time": "0.0", "end_time": "0.5",
                "alternatives": [{"content": "Xin"}],
            }],
        },
    })
    assert result == {
        "text": "Xin chao cloud.",
        "segments": [{"start": 0.0, "end": 0.5, "text": "Xin"}],
    }


def test_s3_transcript_reader_rejects_truncated_body():
    payload = json.dumps({
        "status": "COMPLETED",
        "results": {"transcripts": [{"transcript": "Cloud"}], "items": []},
    }).encode()
    client = Mock()
    client.get_object.return_value = {
        "ContentLength": len(payload) + 1,
        "Body": io.BytesIO(payload),
    }
    with pytest.raises(ValueError, match="Incomplete"):
        S3TranscriptAdapter(client).read("bucket", "ai/transcript.json")


def test_dedicated_handler_is_disabled_without_creating_aws_clients():
    path = ROOT / "infrastructure/lambda/ai_worker_handler.py"
    spec = importlib.util.spec_from_file_location("ai_worker_handler_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch("boto3.client") as client:
        spec.loader.exec_module(module)
        with patch.object(settings, "AI_WORKER_ENABLED", False), pytest.raises(
            ai_worker_service.AIWorkerError, match="AI_WORKER_DISABLED",
        ):
            module.handler({}, None)
    client.assert_not_called()


def test_handler_retries_only_retryable_aws_errors():
    path = ROOT / "infrastructure/lambda/ai_worker_handler.py"
    spec = importlib.util.spec_from_file_location("ai_worker_handler_errors", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    event = {"action": "generate_content", "run_id": RUN_ID, "execution_arn": OWNER}

    denied = ClientError(
        {"Error": {"Code": "AccessDeniedException"},
         "ResponseMetadata": {"HTTPStatusCode": 403}},
        "InvokeModel",
    )
    with (
        patch.object(settings, "AI_WORKER_ENABLED", True),
        patch.object(module, "_execute", side_effect=denied),
        pytest.raises(ai_worker_service.AIWorkerError) as permanent,
    ):
        module.handler(event, None)
    assert type(permanent.value) is ai_worker_service.AIWorkerError

    throttled = ClientError(
        {"Error": {"Code": "ThrottlingException"},
         "ResponseMetadata": {"HTTPStatusCode": 429}},
        "InvokeModel",
    )
    with (
        patch.object(settings, "AI_WORKER_ENABLED", True),
        patch.object(module, "_execute", side_effect=throttled),
        pytest.raises(ai_worker_service.AIWorkerTemporaryError),
    ):
        module.handler(event, None)


def test_handler_rejects_wrong_aws_region_before_dependencies():
    path = ROOT / "infrastructure/lambda/ai_worker_handler.py"
    spec = importlib.util.spec_from_file_location("ai_worker_handler_region", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with (
        patch.object(settings, "AI_WORKER_ENABLED", True),
        patch.object(settings, "AWS_REGION", "us-east-1"),
        patch.object(module, "_execute") as execute,
        pytest.raises(ai_worker_service.AIWorkerError, match="INVALID_AI_WORKER_REGION"),
    ):
        module.handler({}, None)
    execute.assert_not_called()
