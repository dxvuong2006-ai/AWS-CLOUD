"""K5 AI worker orchestration; AWS waits remain in Step Functions, not Lambda."""

import logging
import re

from app.config import settings
from app.repositories import review_repo
from app.schemas.review import DraftContent
from app.services import video_pipeline_service

logger = logging.getLogger(__name__)


class AIWorkerError(Exception):
    """Only constant, non-sensitive codes cross the Lambda boundary."""


class AIWorkerTemporaryError(AIWorkerError):
    pass


def transcription_job_name(run_id: str) -> str:
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{64}", run_id):
        raise AIWorkerError("INVALID_RUN_ID")
    return f"learncloud-k5-{run_id}"


def transcription_output(run_id: str) -> tuple[str, str]:
    bucket = settings.TRANSCRIBE_OUTPUT_BUCKET or settings.S3_BUCKET
    prefix = settings.TRANSCRIBE_OUTPUT_PREFIX.strip("/")
    if not prefix or ".." in prefix or "\\" in prefix:
        raise AIWorkerError("INVALID_TRANSCRIBE_OUTPUT_PREFIX")
    return bucket, f"{prefix}/{run_id}/transcript.json"


def _video_ready(db, run_id, execution_arn):
    try:
        run, lesson, _ = video_pipeline_service._owned(db, run_id, execution_arn)
    except video_pipeline_service.PipelineError as exc:
        raise AIWorkerError(str(exc)) from None
    if run.state != "VIDEO_READY" or lesson.processed_video_key != run.output_key:
        raise AIWorkerError("VIDEO_NOT_READY")
    return run, lesson


def _content_complete(db, run, lesson) -> bool:
    transcript = lesson.transcript_json
    if (
        not isinstance(transcript, dict)
        or transcript.get("run_id") != run.id
        or not isinstance(transcript.get("text"), str)
        or not transcript["text"].strip()
        or not isinstance(lesson.summary, str)
        or not lesson.summary.strip()
        or not isinstance(lesson.key_concepts_json, list)
        or not lesson.key_concepts_json
    ):
        return False
    quiz = review_repo.get_quiz(db, lesson.section_id)
    return bool(
        quiz is not None
        and review_repo.get_questions(db, quiz.id)
        and review_repo.get_flashcards(db, lesson.id)
    )


def start_transcription(db, run_id, execution_arn, transcriber):
    run, lesson = _video_ready(db, run_id, execution_arn)
    job_id = transcription_job_name(run.id)
    bucket, key = transcription_output(run.id)
    if _content_complete(db, run, lesson):
        return {"job_id": job_id, "status": "COMPLETED"}
    lesson.status = "TRANSCRIBING"
    db.commit()  # release DB locks before calling AWS
    result = transcriber.start_job(
        f"s3://{settings.S3_BUCKET}/{run.output_key}",
        job_name=job_id,
        language_code=settings.TRANSCRIBE_LANGUAGE_CODE,
        output_bucket=bucket,
        output_key=key,
        allow_fallback=False,
    )
    if result.get("job_id") != job_id or result.get("status") not in {
        "QUEUED", "IN_PROGRESS", "COMPLETED",
    }:
        raise AIWorkerError("INVALID_TRANSCRIBE_RESPONSE")
    logger.info("ai_transcription_started lesson_id=%s run_id=%s", run.lesson_id, run.id)
    return {"job_id": job_id, "status": result["status"]}


def poll_transcription(db, run_id, execution_arn, job_id, transcriber):
    run, lesson = _video_ready(db, run_id, execution_arn)
    expected = transcription_job_name(run.id)
    if job_id != expected:
        raise AIWorkerError("TRANSCRIBE_JOB_MISMATCH")
    result = transcriber.get_job_status(job_id)
    status = result.get("status")
    if status == "FAILED":
        raise AIWorkerError("TRANSCRIPTION_FAILED")
    if status not in {"QUEUED", "IN_PROGRESS", "COMPLETED"}:
        raise AIWorkerError("INVALID_TRANSCRIBE_RESPONSE")
    if status == "COMPLETED":
        lesson.status = "AI_PROCESSING"
        db.commit()
    return {"job_id": job_id, "status": status}


def _draft(transcript_text: str, ai) -> DraftContent:
    summary = ai.generate_summary(transcript_text)
    concepts = ai.extract_key_concepts(transcript_text)
    quiz = ai.generate_quiz(
        transcript_text, num_questions=settings.AI_QUIZ_QUESTION_COUNT,
    )
    return DraftContent(
        title=summary["title"],
        summary=summary["summary"],
        key_concepts=concepts,
        quiz_title=summary["title"],
        questions=quiz["questions"],
        flashcards=[
            {"front": item["term"], "back": item["definition"], "position": position}
            for position, item in enumerate(concepts, 1)
        ],
    )


def generate_content(
    db, run_id, execution_arn, job_id, *, transcriber, transcript_store, ai,
):
    run, lesson = _video_ready(db, run_id, execution_arn)
    expected = transcription_job_name(run.id)
    if job_id != expected:
        raise AIWorkerError("TRANSCRIBE_JOB_MISMATCH")
    if _content_complete(db, run, lesson):
        db.commit()
        return {"completed": True, "run_id": run.id}
    db.commit()  # never retain row locks during AWS calls

    status = transcriber.get_job_status(job_id).get("status")
    if status != "COMPLETED":
        raise AIWorkerError("TRANSCRIPTION_NOT_COMPLETE")
    bucket, key = transcription_output(run.id)
    transcript = transcript_store.read(bucket, key)
    content = _draft(transcript["text"], ai)

    with review_repo.transaction(db):
        run, lesson = _video_ready(db, run_id, execution_arn)
        review_repo.lock_section(db, lesson.id)
        if _content_complete(db, run, lesson):
            return {"completed": True, "run_id": run.id}
        quiz = review_repo.get_quiz(db, lesson.section_id, lock=True)
        if quiz is not None and review_repo.has_attempts(db, quiz.id):
            raise AIWorkerError("QUIZ_HAS_ATTEMPTS")
        review_repo.replace_content(
            db, lesson, quiz, content, set_review_status=False,
        )
        lesson.transcript_json = {
            "run_id": run.id,
            "job_id": job_id,
            "source": "aws_transcribe",
            "language": settings.TRANSCRIBE_LANGUAGE_CODE,
            "text": transcript["text"],
            "segments": transcript["segments"],
        }
        lesson.status = "AI_PROCESSING"
        lesson.error_message = None
    logger.info(
        "ai_content_persisted lesson_id=%s run_id=%s",
        run.lesson_id, run.id,
    )
    return {"completed": True, "run_id": run.id}
