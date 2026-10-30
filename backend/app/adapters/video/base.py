from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VideoProcessingRequest:
    lesson_id: int
    attempt: int
    source_key: str

    def __post_init__(self):
        if self.lesson_id < 1 or self.attempt < 1 or not self.source_key.strip():
            raise ValueError("Invalid processing request.")

    @property
    def job_id(self) -> str:
        return f"lesson-{self.lesson_id}-retry-{self.attempt}"


@dataclass(frozen=True)
class ProcessingReceipt:
    job_id: str


class ProcessorDispatchError(Exception):
    pass


class VideoProcessor(Protocol):
    def start(self, request: VideoProcessingRequest) -> ProcessingReceipt:
        """Durably accept a job; job_id must be an idempotency key, not a random ID.

        Acceptance never means video/AI processing or approval has completed.
        A future external dispatcher needs an outbox/reconciliation strategy.
        """
        ...
