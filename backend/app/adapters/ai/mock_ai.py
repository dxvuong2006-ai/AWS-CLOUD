"""Development/test AI adapter backed by fixed pipeline fixtures."""

from app.adapters._fixtures import load_json_fixture
from app.adapters.ai.base import BaseAIAdapter


def _load_fixture(filename: str) -> dict:
    data = load_json_fixture(filename)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in fixture: {filename}")
    return data


class MockAIAdapter(BaseAIAdapter):
    """Return fixed sample outputs; never use this adapter in production."""

    def generate_summary(self, transcript: str) -> dict:
        """Return the sample summary, independent of the supplied transcript."""
        return _load_fixture("summary_sample.json")

    def generate_quiz(self, transcript: str, num_questions: int = 3) -> dict:
        """Return the requested number of sample questions when available."""
        if (
            isinstance(num_questions, bool)
            or not isinstance(num_questions, int)
            or num_questions < 1
        ):
            raise ValueError("num_questions must be a positive integer.")

        quiz = _load_fixture("quiz_sample.json")
        questions = quiz.get("questions")
        if not isinstance(questions, list):
            raise ValueError("Quiz fixture must contain a questions list.")
        if num_questions > len(questions):
            raise ValueError(
                f"Requested {num_questions} questions, but the quiz fixture "
                f"contains only {len(questions)}."
            )
        return {**quiz, "questions": questions[:num_questions]}

    def extract_key_concepts(self, transcript: str) -> list[dict[str, str]]:
        """Return fixed sample concepts, independent of the transcript."""
        concepts = _load_fixture("summary_sample.json").get("key_concepts")
        if not isinstance(concepts, list):
            raise ValueError("Summary fixture must contain a key_concepts list.")
        if any(
            not isinstance(concept, dict)
            or not isinstance(concept.get("term"), str)
            or not isinstance(concept.get("definition"), str)
            for concept in concepts
        ):
            raise ValueError(
                "Each key concept fixture item must contain string term and definition."
            )
        return concepts