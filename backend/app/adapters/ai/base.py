"""Abstract interface for AI-powered lecture processing adapters."""

from abc import ABCMeta, abstractmethod


class BaseAIAdapter(metaclass=ABCMeta):
    """Define the operations provided by an AI adapter."""

    @abstractmethod
    def generate_summary(self, transcript: str) -> dict:
        """Generate a structured summary from a lecture transcript."""
        ...

    @abstractmethod
    def generate_quiz(self, transcript: str, num_questions: int = 3) -> dict:
        """Generate a structured multiple-choice quiz from a transcript."""
        ...

    @abstractmethod
    def extract_key_concepts(self, transcript: str) -> list[dict[str, str]]:
        """Extract key terms and their definitions from a transcript."""
        ...