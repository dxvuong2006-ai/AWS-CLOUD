import boto3

from app.adapters.storage.base import StorageAdapter
from app.config import settings


class S3StorageAdapter(StorageAdapter):

    def __init__(self):
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
        )
        self.bucket = settings.S3_BUCKET

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