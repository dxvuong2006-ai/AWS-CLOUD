#kiểm tra nhanh độ ổn định độc lập khi chạy không cần mạng/cloud (Smoke Test)
"""Run fixture-backed smoke checks with explicit fake AI clients.

Run with python -m ai_pipeline.tests.test_processors_smoke.
Covers explicit clients, legacy fallback, and strict mode without fixtures.
"""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft7Validator

from ai_pipeline.processors import build_summary as summary_module
from ai_pipeline.processors import build_key_concepts as concepts_module
from ai_pipeline.processors._common import AIClientError, meaningful_words
from ai_pipeline.processors.build_key_concepts import build_key_concepts
from ai_pipeline.processors.build_quiz import build_quiz
from ai_pipeline.processors.build_summary import build_summary
from ai_pipeline.processors.normalize_transcript import normalize_transcript

ROOT = Path(__file__).resolve().parents[1]


class ProcessorSmokeTests(unittest.TestCase):
    """Verify output contracts and explicit failure/fallback policies."""
    #Nạp dữ liệu mẫu và kiểm định hợp đồng Schema
    @classmethod
    def setUpClass(cls):
        """Load mock data only inside the test harness."""
        def load(name):
            return json.loads((ROOT / 'fixtures' / name).read_text('utf-8'))

        cls.transcript = normalize_transcript(load('transcript_sample.json'))
        cls.summary = load('summary_sample.json')
        cls.quiz = load('quiz_sample.json')

    def test_fixture_pipeline(self):
        """Exercise all four processors using explicit fixture clients."""
        text = self.transcript['full_text']
        self.assertGreater(self.transcript['word_count'], 0)
        self.assertTrue(self.transcript['segments'])
        summary = build_summary(text, lambda _: self.summary)
        concepts = build_key_concepts(
            text, lambda _: {'key_concepts': self.summary['key_concepts']}
        )
        quiz = build_quiz(text, lambda _: self.quiz)
        for name, data in [('summary', summary), ('quiz', quiz)]:
            schema = json.loads(
                (ROOT / 'schemas' / f'{name}.schema.json').read_text('utf-8')
            )
            Draft7Validator(schema).validate(data)
        self.assertEqual(concepts, self.summary['key_concepts'])
        self.assertEqual(set(summary), {'title', 'summary', 'key_concepts'})
        self.assertEqual(set(quiz), {'questions'})
        self.assertIn('options', quiz['questions'][0])

    #Chính sách riêng biệt của bộ tạo trắc nghiệm
    def test_quiz_fallback_default_and_strict_mode(self):
        with patch.object(Path, 'open', side_effect=AssertionError('file IO')):
            with self.assertRaises(AIClientError):
                build_quiz(
                    self.transcript['full_text'], allow_fallback=False
                )
        with self.assertLogs(
            build_quiz.__module__, level='WARNING'
        ) as log:
            quiz = build_quiz(self.transcript['full_text'])
        self.assertEqual(quiz, self.quiz)
        self.assertIn('source=fixture', log.output[0])

    def test_quiz_provider_failure(self):
        def fail(_):
            raise TimeoutError('provider timeout')

        with self.assertRaises(AIClientError) as error:
            build_quiz('Lecture text.', fail)
        self.assertIsInstance(error.exception.__cause__, TimeoutError)


    def test_quiz_rejects_malformed_response(self):
        with self.assertRaises(ValueError):
            build_quiz('Lecture text.', lambda _: 'not-json')

    #Kiểm tra chính sách dự phòng và chế độ nghiêm ngặt
    def test_fallback_default_and_strict_mode(self):
        for builder in (build_summary, build_key_concepts):
            with self.subTest(builder=builder.__name__):
                with self.assertRaises(AIClientError):
                    builder(
                        'A database is a collection of data.',
                        allow_fallback=False,
                    )
                with self.assertLogs(
                    builder.__module__, level='WARNING'
                ) as log:
                    result = builder(
                        'A database is a collection of data.',
                    )
                self.assertTrue(result)
                self.assertIn('source=heuristic', log.output[0])

    def test_invalid_json_fallback_policy(self):
        for builder in (build_summary, build_key_concepts):
            with self.subTest(builder=builder.__name__):
                with self.assertRaises(ValueError):
                    builder(
                        'A database stores data.', lambda _: 'not-json',
                        allow_fallback=False,
                    )
                with self.assertLogs(builder.__module__, level='WARNING'):
                    result = builder(
                        'A database stores data.', lambda _: 'not-json',
                    )
                self.assertTrue(result)

    #Phân định lỗi AI và lỗi lập trình
    def test_known_provider_errors_allow_fallback(self):
        for builder in (build_summary, build_key_concepts):
            for error_type in (AIClientError, TimeoutError, ConnectionError):
                def fail(_, error_type=error_type):
                    raise error_type('provider unavailable')

                with self.subTest(builder=builder.__name__, error=error_type):
                    with self.assertRaises(AIClientError):
                        builder(
                            'A database stores data.', fail,
                            allow_fallback=False,
                        )
                    with self.assertLogs(builder.__module__, level='WARNING'):
                        self.assertTrue(builder(
                            'A database stores data.', fail,
                        ))

    def test_programming_errors_propagate(self):
        for builder in (build_summary, build_key_concepts):
            for error_type in (TypeError, AttributeError, ValueError):
                def fail(_, error_type=error_type):
                    raise error_type('programming defect')

                with self.subTest(builder=builder.__name__, error=error_type):
                    with self.assertRaises(error_type):
                        builder('Lecture text.', fail, allow_fallback=True)

    def test_missing_prompt_fallback_and_strict_mode(self):
        for module, builder in (
            (summary_module, build_summary),
            (concepts_module, build_key_concepts),
        ):
            with self.subTest(builder=builder.__name__):
                with patch.object(
                    module, '_PROMPT_PATH', ROOT / 'missing-prompt.txt'
                ):
                    with self.assertRaises(FileNotFoundError):
                        builder(
                            'Lecture text.', lambda _: self.summary,
                            allow_fallback=False,
                        )
                    with self.assertLogs(builder.__module__, level='WARNING'):
                        self.assertTrue(builder(
                            'Lecture text.', lambda _: self.summary,
                        ))

    #Kiểm thử xử lý dữ liệu xấu và trường hợp biên
    def test_empty_transcript_is_not_content(self):
        for builder in (build_summary, build_key_concepts):
            with self.subTest(builder=builder.__name__):
                with self.assertRaises(ValueError):
                    builder('  ', allow_fallback=True)

    def test_normalization_and_retained_helper(self):
        result = normalize_transcript({
            'segments': [{'text': 'Keep text', 'start': 'NaN', 'end': 2}]
        })
        self.assertEqual(result['full_text'], 'Keep text')
        self.assertEqual(result['segments'], [])
        self.assertEqual(meaningful_words('Cloud and DATA'), {'cloud', 'data'})


if __name__ == '__main__':
    unittest.main()
