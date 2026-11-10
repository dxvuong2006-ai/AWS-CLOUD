"""Read-only video presentation state; never advances the processing pipeline."""
from enum import Enum


class LessonVideoStatus(str, Enum):
    NOT_UPLOADED = "NOT_UPLOADED"
    UPLOAD_PENDING = "UPLOAD_PENDING"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


def video_status(status, has_raw_video, has_processed_video, upload_pending=False):
    if status == "FAILED":
        return LessonVideoStatus.FAILED
    if status in {"PROCESSING", "TRANSCRIBING", "AI_PROCESSING"}:
        return LessonVideoStatus.PROCESSING
    if status == "UPLOADED":
        return LessonVideoStatus.UPLOADED
    if status in {"REVIEW_REQUIRED", "PUBLISHED"}:
        return LessonVideoStatus.READY
    if status == "DRAFT":
        if has_processed_video:
            return LessonVideoStatus.READY
        if has_raw_video:
            return LessonVideoStatus.UPLOADED
        if upload_pending:
            return LessonVideoStatus.UPLOAD_PENDING
        return LessonVideoStatus.NOT_UPLOADED
    return LessonVideoStatus.UNKNOWN
