"""Optional pipeline ledger; migration 0005 must be reviewed/applied by operator."""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, Text, UniqueConstraint, func, text,
)

from app.database import Base


class VideoUpload(Base):
    __tablename__ = "video_uploads"
    __table_args__ = (
        UniqueConstraint("id", "lesson_id", name="uq_video_upload_id_lesson"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 524288000", name="ck_video_upload_size"),
    )
    id = Column(String(32), primary_key=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    source_key = Column(Text, nullable=False, unique=True)
    content_type = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class VideoPipelineRun(Base):
    __tablename__ = "video_pipeline_runs"
    __table_args__ = (
        UniqueConstraint("upload_id", "attempt", name="uq_video_run_upload_attempt"),
        ForeignKeyConstraint(
            ["upload_id", "lesson_id"], ["video_uploads.id", "video_uploads.lesson_id"],
            name="fk_video_run_upload_lesson",
        ),
        CheckConstraint("attempt >= 0", name="ck_video_run_attempt"),
        CheckConstraint("state IN ('QUEUED','CLAIMED','SUBMITTING','TRANSCODING','VIDEO_READY','COMPLETE','FAILED')",
                        name="ck_video_run_state"),
        Index("ix_video_pipeline_outbox", "next_dispatch_at",
              postgresql_where=text("state = 'QUEUED'"), sqlite_where=text("state = 'QUEUED'")),
    )
    id = Column(String(64), primary_key=True)
    upload_id = Column(String(32), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    attempt = Column(Integer, nullable=False)  # equals Lesson.retry_count; initial = 0
    state = Column(String(24), nullable=False)
    execution_arn = Column(Text, nullable=True, unique=True)
    source_etag = Column(String(128), nullable=False)
    output_key = Column(Text, nullable=False)
    job_id = Column(String(128), nullable=True)
    error_code = Column(String(64), nullable=True)
    safe_to_retry = Column(Boolean, nullable=False, default=False, server_default="false")
    next_dispatch_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
