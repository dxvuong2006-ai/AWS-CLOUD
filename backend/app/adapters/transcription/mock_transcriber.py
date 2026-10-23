import json
from pathlib import Path


_TRANSCRIPT_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "ai_pipeline"
    / "fixtures"
    / "transcript_sample.json"
)


class MockTranscriber:
    def transcribe(
        self,
        media_path: str,
        language_code: str = "vi-VN",
    ) -> dict:
        with _TRANSCRIPT_FIXTURE.open(encoding="utf-8") as fixture_file:
            transcript = json.load(fixture_file)
        if not isinstance(transcript, dict):
            raise ValueError(
                f"Expected a JSON object in fixture: {_TRANSCRIPT_FIXTURE}"
            )
        return transcript

    def get_job_status(self, job_id: str) -> dict:
        return {"status": "COMPLETED", "job_id": job_id}


if __name__ == "__main__":
    transcriber = MockTranscriber()
    transcript_data = transcriber.transcribe("dummy.mp4")
    print(len(transcript_data.get("segments", [])))
