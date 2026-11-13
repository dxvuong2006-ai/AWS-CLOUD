from pathlib import Path
from pydantic import Field, SecretStr

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str = ""

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
    AI_WORKER_ENABLED: bool = False
    TRANSCRIBE_LANGUAGE_CODE: str = "vi-VN"
    TRANSCRIBE_OUTPUT_BUCKET: str = ""
    TRANSCRIBE_OUTPUT_PREFIX: str = "ai-transcripts"
    AI_TRANSCRIPT_MAX_BYTES: int = Field(default=2_000_000, ge=1_000, le=5_000_000)
    AI_TRANSCRIPT_MAX_CHARACTERS: int = Field(
        default=400_000, ge=1_000, le=1_000_000,
    )
    BEDROCK_MODEL_ID: str = "apac.amazon.nova-micro-v1:0"
    AI_QUIZ_QUESTION_COUNT: int = Field(default=3, ge=1, le=20)

    JWT_SECRET_KEY: SecretStr | None = None
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)
    COGNITO_REGION: str = ""
    COGNITO_USER_POOL_ID: str = ""
    COGNITO_APP_CLIENT_ID: str = ""

    # Independent of the frontend selector; never accepted in production.
    LOCAL_AUTH_ENABLED: bool = False
    LOCAL_AUTH_JWT_SECRET: SecretStr | None = None
    LOCAL_AUTH_JWT_ISSUER: str = "learncloud-local"
    LOCAL_AUTH_JWT_AUDIENCE: str = "learncloud-api"
    LOCAL_AUTH_OTP_TTL_SECONDS: int = Field(default=600, ge=60, le=1800)
    LOCAL_AUTH_RESEND_SECONDS: int = Field(default=60, ge=30, le=600)
    LOCAL_AUTH_OTP_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=10)
    LOCAL_AUTH_LOGIN_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    LOCAL_AUTH_LOGIN_LOCK_SECONDS: int = Field(default=300, ge=60, le=3600)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = Field(default=1025, ge=1, le=65535)
    SMTP_FROM: str = "LearnCloud <no-reply@learncloud.test>"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
