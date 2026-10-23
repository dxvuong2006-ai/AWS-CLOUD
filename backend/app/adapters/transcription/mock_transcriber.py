from app.adapters._fixtures import load_json_fixture


class MockTranscriber:
    """Return a fixed transcript fixture for development and tests."""

    def transcribe(
        self,
        media_path: str,
        language_code: str = "vi-VN",
    ) -> dict:
        """Return the sample payload; media_path and language_code are ignored."""
        transcript = load_json_fixture("transcript_sample.json")
        if not isinstance(transcript, dict):
            raise ValueError("Expected a JSON object in transcript_sample.json.")
        if not isinstance(transcript.get("segments"), list):
            raise ValueError("Transcript fixture must contain a segments list.")
        return transcript

    def get_job_status(self, job_id: str) -> dict:
        return {"status": "COMPLETED", "job_id": job_id}


if __name__ == "__main__":
    transcriber = MockTranscriber()
    transcript_data = transcriber.transcribe("dummy.mp4")
    print(len(transcript_data.get("segments", [])))
