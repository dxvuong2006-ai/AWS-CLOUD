"""Read and validate an Amazon Transcribe result from a controlled S3 key."""

import json
import math

import boto3
from botocore.config import Config

from app.config import settings


class S3TranscriptAdapter:
    """Small, bounded S3 reader for deterministic Transcribe output objects."""

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3", region_name=settings.AWS_REGION,
                config=Config(
                    connect_timeout=5, read_timeout=15,
                    retries={"total_max_attempts": 2, "mode": "standard"},
                ),
            )
        return self._client

    def read(self, bucket: str, key: str, *, max_bytes: int = 5_000_000) -> dict:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 1 <= max_bytes <= 5_000_000:
            raise ValueError("Invalid Transcribe result size limit.")
        response = self.client.get_object(Bucket=bucket, Key=key)
        length = response.get("ContentLength")
        if not isinstance(length, int) or length <= 0 or length > max_bytes:
            raise ValueError("Invalid Transcribe result size.")
        stream = response["Body"]
        try:
            payload = stream.read(max_bytes + 1)
        finally:
            stream.close()
        if len(payload) > max_bytes:
            raise ValueError("Transcribe result is too large.")
        if len(payload) != length:
            raise ValueError("Incomplete Transcribe result body.")
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Invalid Transcribe result JSON.") from None
        return parse_transcript(document)


def parse_transcript(document: dict) -> dict:
    """Convert the AWS result envelope to LearnCloud's transcript contract."""
    if not isinstance(document, dict) or document.get("status") != "COMPLETED":
        raise ValueError("Transcribe result is not complete.")
    results = document.get("results")
    transcripts = results.get("transcripts") if isinstance(results, dict) else None
    text = transcripts[0].get("transcript") if (
        isinstance(transcripts, list) and transcripts
        and isinstance(transcripts[0], dict)
    ) else None
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Transcribe result has no transcript text.")
    segments = []
    for item in results.get("items", []):
        if not isinstance(item, dict) or item.get("type") != "pronunciation":
            continue
        alternatives = item.get("alternatives")
        content = alternatives[0].get("content") if (
            isinstance(alternatives, list) and alternatives
            and isinstance(alternatives[0], dict)
        ) else None
        try:
            start, end = float(item["start_time"]), float(item["end_time"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if (
            isinstance(content, str)
            and content.strip()
            and math.isfinite(start)
            and math.isfinite(end)
            and 0 <= start <= end
        ):
            segments.append({"start": start, "end": end, "text": content.strip()})
    return {"text": text.strip(), "segments": segments}
