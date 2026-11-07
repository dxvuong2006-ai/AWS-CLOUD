import unittest
from uuid import uuid4
from pydantic import ValidationError
from app.schemas.progress import LessonProgressUpdateRequest
from app.schemas.quiz import QuizAttemptSubmitRequest

class ContractTests(unittest.TestCase):
    def test_client_cannot_assert_completion_or_duration(self):
        for field in ["completed", "progress_percent", "duration_seconds"]:
            with self.assertRaises(ValidationError):
                LessonProgressUpdateRequest(**{
                    "last_position_seconds": 10, "watched_ranges": [[0, 10]], field: 100
                })

    def test_invalid_ranges_rejected(self):
        for ranges in [[[10, 0]], [[-1, 4]], [[0, float("inf")]], [[0, float("nan")]]]:
            with self.assertRaises(ValidationError):
                LessonProgressUpdateRequest(last_position_seconds=0, watched_ranges=ranges)

    def test_empty_answers_valid_but_duplicate_questions_rejected(self):
        self.assertEqual(QuizAttemptSubmitRequest(request_id=uuid4(), answers=[]).answers, [])
        with self.assertRaises(ValidationError):
            QuizAttemptSubmitRequest(request_id=uuid4(), answers=[
                {"question_id": 1, "selected_answer": "A"},
                {"question_id": 1, "selected_answer": "B"},
            ])
