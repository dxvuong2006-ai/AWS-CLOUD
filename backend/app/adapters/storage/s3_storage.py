import boto3
from botocore.config import Config

from app.adapters.storage.base import StorageAdapter
from app.config import settings


class S3StorageAdapter(StorageAdapter):

    def __init__(self):
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
                connect_timeout=5,
                read_timeout=10,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        self.bucket = settings.S3_BUCKET
        # Snapshot the session used by boto3.client; never inspect/log key material.
        session = boto3.DEFAULT_SESSION
        self.profile_name = session.profile_name if session is not None else None
        self.playback_operation = "CreateS3Client"

    def generate_download_url(
        self, object_key: str, content_type: str, expires_in: int = 900
    ) -> str:
        # Signing alone does not verify that an object exists or is readable.
        self.playback_operation = "HeadObject"
        self.head_video(object_key)
        self.playback_operation = "GeneratePresignedGetUrl"
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expires_in,
            HttpMethod="GET",
        )

    def head_video(self, object_key: str) -> dict:
        return self.client.head_object(Bucket=self.bucket, Key=object_key)

    def has_raw_video_objects(self, lesson_id: int) -> bool:
        # Read-only preflight for legacy PUTs that were never recorded in DB.
        prefix = f"lessons/{int(lesson_id)}/raw/"
        result = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix, MaxKeys=2)
        return any(obj.get("Key") != prefix for obj in result.get("Contents", [])) or bool(result.get("IsTruncated"))

    def generate_upload_url(
        self,
        object_key: str,
        content_type: str,
        expires_in: int = 900,
        *,
        prevent_overwrite: bool = False,
    ) -> str:
        params = {"Bucket": self.bucket, "Key": object_key, "ContentType": content_type}
        if prevent_overwrite:
            params["IfNoneMatch"] = "*"
        return self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
