"""Kiểm thử processor Tutor."""

import pytest
from ai_pipeline.processors.build_tutor_context import build_tutor_context


def test_tutor_fallback_uses_incorrect_questions():
    """Fallback giữ đúng câu và đáp án gốc."""
    wrong = [{"question": "Q?", "options": ["a", "b"],
              "correct_answer": "a", "explanation": "E"}]
    result = build_tutor_context("Bài giảng.", wrong)
    assert result["practice_questions"] == wrong


def test_tutor_strict_requires_client():
    """Chế độ nghiêm ngặt từ chối thiếu client."""
    with pytest.raises(RuntimeError):
        build_tutor_context("Bài giảng.", [{"question": "Q"}],
                            allow_fallback=False)
