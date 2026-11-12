"""Kết nối AWS Transcribe cho các tác vụ phiên âm bất đồng bộ."""

import logging
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError, ConnectionClosedError, ConnectTimeoutError,
    CredentialRetrievalError, EndpointConnectionError, NoCredentialsError,
    PartialCredentialsError,
)

from app.adapters.transcription.mock_transcriber import MockTranscriber
from app.config import settings

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
        self._mock = None

    def _mock_transcriber(self):
        if self._mock is None:
            self._mock = MockTranscriber()
        return self._mock

    def _get_client(self):
        """Tạo client theo chuỗi credentials mặc định của AWS.

        Returns:
            Client Transcribe đã cấu hình.
        """
        if self._client is None:
            self._client = boto3.client(
                "transcribe",
                region_name=settings.AWS_REGION,
                config=Config(
                    connect_timeout=5,
                    read_timeout=15,
                    retries={"total_max_attempts": 2, "mode": "standard"},
                ),
            )
        return self._client

    def transcribe(
        self, media_path_or_s3_uri, language_code="vi-VN",
        allow_fallback=False,
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
            result = self._mock_transcriber().transcribe(
                media_path_or_s3_uri, language_code,
            )
            self._mock_jobs.add(job_id)
            return {**result, "job_id": job_id, "source": "mock"}
        job = response["TranscriptionJob"]
        return {"job_id": job["TranscriptionJobName"],
                "status": job["TranscriptionJobStatus"], "source": "aws"}

    def start_job(
        self, media_uri, *, job_name, language_code="vi-VN",
        output_bucket=None, output_key=None, allow_fallback=False,
    ):
        """Start a deterministic job; a retry reuses the existing AWS job.

        Production callers must leave ``allow_fallback`` disabled.  A stable
        job name makes a Lambda timeout after StartTranscriptionJob safe to
        retry without creating a second transcription job.
        """
        if not isinstance(media_uri, str) or not media_uri.startswith("s3://"):
            raise ValueError("AWS Transcribe requires an s3:// media URI.")
        if not isinstance(job_name, str) or not re.fullmatch(
            r"[A-Za-z0-9._-]{1,200}", job_name,
        ):
            raise ValueError("Invalid Transcribe job name.")
        if bool(output_bucket) != bool(output_key):
            raise ValueError("Transcribe output bucket and key must be provided together.")
        request = {
            "TranscriptionJobName": job_name,
            "Media": {"MediaFileUri": media_uri},
            "LanguageCode": language_code,
        }
        if output_bucket:
            request.update(OutputBucketName=output_bucket, OutputKey=output_key)
        try:
            response = self._get_client().start_transcription_job(**request)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConflictException":
                existing = self._get_client().get_transcription_job(
                    TranscriptionJobName=job_name,
                )["TranscriptionJob"]
                if (
                    existing.get("TranscriptionJobName") != job_name
                    or existing.get("Media", {}).get("MediaFileUri") != media_uri
                    or existing.get("LanguageCode") != language_code
                ):
                    raise ValueError(
                        "Existing Transcribe job does not match the requested job."
                    ) from None
                return self._job_result(existing)
            if not allow_fallback:
                raise
            logger.warning("Transcribe source=mock; reason=%s", type(exc).__name__)
            result = self._mock_transcriber().transcribe(media_uri, language_code)
            self._mock_jobs.add(job_name)
            return {**result, "job_id": job_name, "source": "mock"}
        except AWS_FAILURES as exc:
            if not allow_fallback:
                raise
            logger.warning("Transcribe source=mock; reason=%s", type(exc).__name__)
            result = self._mock_transcriber().transcribe(media_uri, language_code)
            self._mock_jobs.add(job_name)
            return {**result, "job_id": job_name, "source": "mock"}
        return self._job_result(response["TranscriptionJob"])

    @staticmethod
    def _job_result(job):
        result = {
            "job_id": job["TranscriptionJobName"],
            "status": job["TranscriptionJobStatus"],
            "source": "aws",
        }
        transcript = job.get("Transcript")
        if isinstance(transcript, dict):
            result["transcript_uri"] = transcript.get("TranscriptFileUri")
        return result

    def get_job_status(self, job_id):
        """Lấy trạng thái tác vụ thật hoặc tác vụ mô phỏng đã tạo.

        Args:
            job_id: Mã tác vụ được trả khi bắt đầu phiên âm.

        Returns:
            Trạng thái và URI kết quả khi AWS đã hoàn tất.
        """
        if job_id in self._mock_jobs:
            return self._mock_transcriber().get_job_status(job_id)
        job = self._get_client().get_transcription_job(
            TranscriptionJobName=job_id,
        )["TranscriptionJob"]
        result = self._job_result(job)
        if "Transcript" in job:
            result["transcript_uri"] = job["Transcript"].get("TranscriptFileUri")
        if "FailureReason" in job:
            result["failure_reason"] = job["FailureReason"]
        return result
