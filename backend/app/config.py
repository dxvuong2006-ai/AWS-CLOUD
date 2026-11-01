from pathlib import Path
from pydantic import Field, SecretStr

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str

    # cấu hình S3
    S3_BUCKET: str = "learncloud-videos-mentorcloud"
    AWS_REGION: str = "ap-southeast-1"

    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()