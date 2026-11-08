"""Kết nối AWS Transcribe cho các tác vụ phiên âm bất đồng bộ."""

import logging
import uuid

import boto3
from botocore.exceptions import (
    ClientError, ConnectionClosedError, ConnectTimeoutError,
    CredentialRetrievalError, EndpointConnectionError, NoCredentialsError,
    PartialCredentialsError,
)

from app.adapters.transcription.mock_transcriber import MockTranscriber

logger = logging.getLogger(__name__)
AWS_FAILURES = (
    ClientError, ConnectionClosedError, ConnectTimeoutError,
    CredentialRetrievalError, EndpointConnectionError, NoCredentialsError,
    PartialCredentialsError,
)


class AWSTranscribeAdapter:
    """Tạo và theo dõi tác vụ Transcribe qua AWS SDK."""

    def __init__(self, client=None):
        """Khởi tạo client tùy chọn để hỗ trợ kiểm thử.

        Args:
            client: Client Transcribe được tiêm hoặc None.
        """
        self._client = client
        self._mock_jobs = set()
        self._mock = MockTranscriber()

    def _get_client(self):
        """Tạo client theo chuỗi credentials mặc định của AWS.

        Returns:
            Client Transcribe đã cấu hình.
        """
        if self._client is None:
            self._client = boto3.client("transcribe")
        return self._client

    def transcribe(
        self, media_path_or_s3_uri, language_code="vi-VN",
        allow_fallback=True,
    ):
        """Tạo tác vụ phiên âm cho media đã tải lên S3.

        Args:
            media_path_or_s3_uri: URI S3 của tệp media.
            language_code: Mã ngôn ngữ nhận dạng.
            allow_fallback: Cho phép dữ liệu mẫu khi AWS gặp lỗi.

        Returns:
            Trạng thái và job_id của tác vụ, hoặc transcript mẫu khi fallback.
        """
        if not media_path_or_s3_uri.startswith("s3://"):
            raise ValueError("AWS Transcribe requires an s3:// media URI.")
        job_id = "learncloud-" + uuid.uuid4().hex
        try:
            response = self._get_client().start_transcription_job(
                TranscriptionJobName=job_id,
                Media={"MediaFileUri": media_path_or_s3_uri},
                LanguageCode=language_code,
            )
        except AWS_FAILURES as exc:
            if not allow_fallback:
                raise
            logger.warning("Transcribe source=mock; reason=%s", type(exc).__name__)
            result = self._mock.transcribe(media_path_or_s3_uri, language_code)
            self._mock_jobs.add(job_id)
            return {**result, "job_id": job_id, "source": "mock"}
        job = response["TranscriptionJob"]
        return {"job_id": job["TranscriptionJobName"],
                "status": job["TranscriptionJobStatus"], "source": "aws"}

    def get_job_status(self, job_id):
        """Lấy trạng thái tác vụ thật hoặc tác vụ mô phỏng đã tạo.

        Args:
            job_id: Mã tác vụ được trả khi bắt đầu phiên âm.

        Returns:
            Trạng thái và URI kết quả khi AWS đã hoàn tất.
        """
        if job_id in self._mock_jobs:
            return self._mock.get_job_status(job_id)
        job = self._get_client().get_transcription_job(
            TranscriptionJobName=job_id,
        )["TranscriptionJob"]
        result = {"job_id": job_id, "status": job["TranscriptionJobStatus"]}
        if "Transcript" in job:
            result["transcript_uri"] = job["Transcript"].get("TranscriptFileUri")
        if "FailureReason" in job:
            result["failure_reason"] = job["FailureReason"]
        return result


def process_video_pipeline(
    video_s3_key_or_path, lesson_id, db, *, instructor_id,
    transcriber=None, ai=None,
):
    """Khởi tạo phiên âm và lưu nháp khi transcript đã sẵn sàng.

    Args:
        video_s3_key_or_path: URI S3 hoặc đường dẫn cho transcriber giả lập.
        lesson_id: Mã bài học.
        db: Session hiện tại.
        instructor_id: Giảng viên sở hữu khóa học.
        transcriber: Adapter phiên âm tùy chọn.
        ai: Adapter AI tùy chọn.

    Returns:
        Trạng thái job đang chạy hoặc bản nháp REVIEW_REQUIRED.
    """
    from ai_pipeline.processors.normalize_transcript import normalize_transcript
    from app.adapters.ai.bedrock_ai import BedrockAIAdapter
    from app.schemas.review import DraftGeneration
    from app.services import review_service

    review_service._owned_lesson(db, lesson_id, instructor_id)
    transcriber = transcriber or AWSTranscribeAdapter()
    ai = ai or BedrockAIAdapter(allow_fallback=True)
    raw = transcriber.transcribe(video_s3_key_or_path)
    if "segments" not in raw and "full_text" not in raw:
        return {"status": raw["status"], "job_id": raw["job_id"]}
    transcript = normalize_transcript(raw)
    if not transcript["full_text"].strip():
        raise ValueError("Transcription returned no text.")
    draft = review_service.generate_draft(
        db, lesson_id=lesson_id, instructor_id=instructor_id,
        payload=DraftGeneration(transcript=transcript["full_text"]),
        ai=ai, transcript_data=transcript,
    )
    return {"status": "REVIEW_REQUIRED", "draft": draft}

