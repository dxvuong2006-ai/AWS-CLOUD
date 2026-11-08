from pathlib import Path
from pydantic import Field, SecretStr

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str

    # cấu hình S3
    S3_BUCKET: str = "learncloud-videos-mentorcloud"
    AWS_REGION: str = "ap-southeast-1"
    APP_ENV: str = "production"
    ALLOW_RAW_VIDEO_PLAYBACK: bool = False
    VIDEO_URL_EXPIRES_IN: int = Field(default=900, ge=60, le=3600)
    VIDEO_PROCESSOR_BACKEND: str = "disabled"
    LOCAL_VIDEO_JOB_DIR: Path = PROJECT_ROOT / ".local-video-jobs"
    VIDEO_PIPELINE_ENABLED: bool = False
    MEDIACONVERT_ROLE_ARN: str = ""
    MEDIACONVERT_QUEUE_ARN: str = ""
    VIDEO_EVENT_BUS: str = "default"
    VIDEO_AI_ENABLED: bool = False

    JWT_SECRET_KEY: SecretStr | None = None
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)
    COGNITO_REGION: str = ""
    COGNITO_USER_POOL_ID: str = ""
    COGNITO_APP_CLIENT_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
