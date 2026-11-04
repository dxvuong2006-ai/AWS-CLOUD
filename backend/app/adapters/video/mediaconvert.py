"""MediaConvert boundary. Construction and payload building perform no AWS I/O."""
from dataclasses import dataclass
import hashlib
import logging
import re

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.adapters.video.base import ProcessingReceipt, ProcessorDispatchError, VideoProcessingRequest

logger = logging.getLogger(__name__)
RAW_KEY = re.compile(r"lessons/([1-9][0-9]*)/raw/([a-f0-9]{32})\.(mp4|webm|mov)\Z")
ROLE_ARN = re.compile(r"arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9_+=,.@/\-]+\Z")
BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]\Z")
RETRYABLE_CODES = {"TooManyRequestsException", "ThrottlingException", "InternalServerErrorException", "ServiceUnavailableException"}


class MediaConvertError(ProcessorDispatchError):
    def __init__(self, code: str, *, retryable: bool = False, submission_uncertain: bool = True):
        self.code = code
        self.retryable = retryable
        self.submission_uncertain = submission_uncertain
        super().__init__(code)  # Never expose SDK exception text, URLs or credentials.


@dataclass(frozen=True)
class MediaConvertConfig:
    bucket: str
    role_arn: str
    region: str = "ap-southeast-1"
    queue_arn: str = ""

    def __post_init__(self):
        if (not BUCKET.fullmatch(self.bucket) or ".." in self.bucket
                or re.fullmatch(r"[0-9.]+", self.bucket)):
            raise ValueError("Invalid video bucket.")
        if not ROLE_ARN.fullmatch(self.role_arn):
            raise ValueError("MediaConvert service role is required.")
        if self.region != "ap-southeast-1":
            raise ValueError("This pipeline requires ap-southeast-1.")
        if self.queue_arn and not re.fullmatch(
            r"arn:aws:mediaconvert:ap-southeast-1:[0-9]{12}:queues/[A-Za-z0-9_\-]+", self.queue_arn
        ):
            raise ValueError("Invalid MediaConvert queue ARN.")


def source_identity(key: str, lesson_id: int | None = None) -> tuple[int, str]:
    # Generated ASCII keys only. Do not URL-decode or accept arbitrary s3:// URLs.
    match = RAW_KEY.fullmatch(key) if isinstance(key, str) else None
    if match is None or (lesson_id is not None and int(match[1]) != lesson_id):
        raise ValueError("Invalid raw video identity.")
    return int(match[1]), match[2]


def output_key(request: VideoProcessingRequest) -> str:
    _, upload_id = source_identity(request.source_key, request.lesson_id)
    return f"lessons/{request.lesson_id}/processed/{upload_id}/attempt-{request.attempt}/video_720p.mp4"


def build_job_request(config: MediaConvertConfig, request: VideoProcessingRequest) -> dict:
    _, upload_id = source_identity(request.source_key, request.lesson_id)
    token = hashlib.sha256(f"{config.bucket}:{request.source_key}:{request.attempt}".encode()).hexdigest()
    destination = output_key(request).removesuffix("_720p.mp4")
    payload = {
        "Role": config.role_arn,
        "ClientRequestToken": token,
        "UserMetadata": {"lesson_id": str(request.lesson_id), "request_id": request.job_id, "token": token,
                         "run_id": hashlib.sha256(f"{upload_id}:{request.attempt - 1}".encode()).hexdigest()},
        "Settings": {
            "Inputs": [{
                "FileInput": f"s3://{config.bucket}/{request.source_key}",
                "AudioSelectors": {"Audio Selector 1": {"DefaultSelection": "DEFAULT"}},
                "VideoSelector": {},
            }],
            "OutputGroups": [{
                "Name": "LearnCloud MP4",
                "OutputGroupSettings": {"Type": "FILE_GROUP_SETTINGS", "FileGroupSettings": {
                    "Destination": f"s3://{config.bucket}/{destination}",
                }},
                "Outputs": [{
                    "NameModifier": "_720p",
                    "ContainerSettings": {"Container": "MP4", "Mp4Settings": {"MoovPlacement": "PROGRESSIVE_DOWNLOAD"}},
                    "VideoDescription": {
                        "Width": 1280, "Height": 720, "ScalingBehavior": "FIT_NO_UPSCALE",
                        "CodecSettings": {"Codec": "H_264", "H264Settings": {
                            "RateControlMode": "QVBR", "MaxBitrate": 3000000,
                            "QvbrSettings": {"QvbrQualityLevel": 7},
                            "SceneChangeDetect": "TRANSITION_DETECTION",
                        }},
                    },
                    "AudioDescriptions": [{"AudioSourceName": "Audio Selector 1", "CodecSettings": {
                        "Codec": "AAC", "AacSettings": {
                            "Bitrate": 128000, "CodingMode": "CODING_MODE_2_0", "SampleRate": 48000,
                        },
                    }}],
                }],
            }],
        },
    }
    if config.queue_arn:
        payload["Queue"] = config.queue_arn
    return payload


class MediaConvertAdapter:
    def __init__(self, config: MediaConvertConfig, *, client=None):
        self.config = config
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("mediaconvert", region_name=self.config.region, config=Config(
                connect_timeout=3, read_timeout=10,
                retries={"mode": "standard", "total_max_attempts": 2},
            ))
        return self._client

    def build_job_request(self, request: VideoProcessingRequest) -> dict:
        return build_job_request(self.config, request)

    def _call(self, operation: str, **kwargs) -> dict:
        try:
            return getattr(self.client, operation)(**kwargs)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            retryable = code in RETRYABLE_CODES or exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) >= 500
            logger.warning("mediaconvert_failed operation=%s retryable=%s", operation, retryable)
            definite_rejection = code in {"AccessDeniedException", "ForbiddenException", "BadRequestException", "ValidationException", "TooManyRequestsException", "ThrottlingException", "NotFoundException"}
            raise MediaConvertError("MEDIACONVERT_RETRYABLE" if retryable else "MEDIACONVERT_REJECTED",
                                    retryable=retryable, submission_uncertain=not definite_rejection) from None
        except BotoCoreError:
            logger.warning("mediaconvert_failed operation=%s retryable=true", operation)
            raise MediaConvertError("MEDIACONVERT_UNAVAILABLE", retryable=True) from None

    def start(self, request: VideoProcessingRequest) -> ProcessingReceipt:
        """One submission. Caller must persist/fence it; SDK token lasts one minute.

        Never wrap CreateJob in an unbounded retry. A timeout may mean acceptance;
        reconcile an ambiguous submission instead of submitting another job.
        """
        result = self._call("create_job", **self.build_job_request(request))
        job_id = result.get("Job", {}).get("Id")
        if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", job_id):
            raise MediaConvertError("MEDIACONVERT_INVALID_RESPONSE")
        return ProcessingReceipt(job_id=job_id)

    def get_job(self, job_id: str) -> dict:
        if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", job_id):
            raise ValueError("Invalid MediaConvert job ID.")
        return self._call("get_job", Id=job_id)["Job"]

    def cancel_job(self, job_id: str) -> None:
        self._call("cancel_job", Id=job_id)
