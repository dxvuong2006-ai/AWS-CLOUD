from enum import Enum


class LessonStatus(str, Enum):
    DRAFT = "DRAFT"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    TRANSCRIBING = "TRANSCRIBING"
    AI_PROCESSING = "AI_PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


LESSON_STATUS_CHECK = "status IN (" + ", ".join(f"'{state.value}'" for state in LessonStatus) + ")"
