from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str

    # cấu hình S3
    S3_BUCKET: str = "learncloud-videos-mentorcloud"
    AWS_REGION: str = "ap-southeast-1"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()