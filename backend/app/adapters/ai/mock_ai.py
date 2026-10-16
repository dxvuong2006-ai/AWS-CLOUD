"""Local mock implementation of the AI adapter backed by pipeline fixtures."""

import json
from pathlib import Path

from app.adapters.ai.base import BaseAIAdapter


_FIXTURES_DIR = (
    Path(__file__).resolve().parents[4] / "ai_pipeline" / "fixtures"
)


def _load_fixture(filename: str) -> dict:
    """Load a JSON object from the repository's AI pipeline fixtures."""
    fixture_path = _FIXTURES_DIR / filename
    with fixture_path.open(encoding="utf-8") as fixture_file:
        data = json.load(fixture_file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in fixture: {fixture_path}")
    return data


class MockAIAdapter(BaseAIAdapter):
    """Return deterministic AI outputs from local sample fixtures."""

    def generate_summary(self, transcript: str) -> dict:
        """Return the fixed sample summary, independent of the transcript."""
        return _load_fixture("summary_sample.json")

    def generate_quiz(self, transcript: str) -> dict:
        """Return the fixed sample quiz, independent of the transcript."""
        return _load_fixture("quiz_sample.json")

    def extract_key_concepts(self, transcript: str) -> list:
        """Return fixed sample concepts, independent of the transcript."""
        summary = _load_fixture("summary_sample.json")
        concepts = summary.get("key_concepts")
        if not isinstance(concepts, list):
            raise ValueError("Summary fixture must contain a key_concepts list.")
        return concepts