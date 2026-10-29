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
        self.client.head_object(Bucket=self.bucket, Key=object_key)
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

    def generate_upload_url(
        self,
        object_key: str,
        content_type: str,
        expires_in: int = 900,
    ) -> str:

        return self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
