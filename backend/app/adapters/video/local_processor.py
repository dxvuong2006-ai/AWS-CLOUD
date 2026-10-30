"""Development-only, durable local dispatch queue. No transcoding or AI worker.

Pending manifests are requests, not completed results. Before executing one, a
future worker must verify lesson.status=PROCESSING and retry_count=attempt in DB.
This makes a manifest left behind by a failed DB commit ineligible for execution.
"""
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.adapters.video.base import ProcessingReceipt, ProcessorDispatchError, VideoProcessingRequest


class LocalProcessor:
    def __init__(self, job_directory: Path):
        self.job_directory = Path(job_directory)

    def start(self, request: VideoProcessingRequest) -> ProcessingReceipt:
        payload = {"version": 1, "kind": "local_pending_request", **asdict(request)}
        temporary = None
        try:
            self.job_directory.mkdir(parents=True, exist_ok=True)
            destination = self.job_directory / f"{request.job_id}.json"
            # Prepare fully written data, then atomically create without overwrite.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.job_directory, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(payload, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if json.loads(destination.read_text(encoding="utf-8")) != payload:
                    raise ProcessorDispatchError("Processing request conflicts with an existing job.")
        except (OSError, ValueError):
            raise ProcessorDispatchError("Local processing queue is unavailable.") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
        return ProcessingReceipt(job_id=request.job_id)
