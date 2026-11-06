"""Tạo nội dung ôn tập dựa trên transcript và câu trả lời sai."""

import logging
from pathlib import Path

from ._common import call_ai_client, parse_json_response, render_prompt

logger = logging.getLogger(__name__)


def build_tutor_context(transcript, incorrect_answers, ai_client=None, *,
                        allow_fallback=True):
    """Tạo giải thích và câu luyện tập từ dữ liệu bài giảng.

    Args:
        transcript: Văn bản bài giảng.
        incorrect_answers: Câu hỏi sai cùng phương án và đáp án.
        ai_client: Client AI tùy chọn.
        allow_fallback: Cho phép sử dụng câu hỏi gốc khi AI lỗi.

    Returns:
        Đối tượng explanation và practice_questions.
    """
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError("Transcript is required.")
    if not incorrect_answers:
        raise ValueError("At least one incorrect answer is required.")
    if ai_client is not None:
        try:
            prompt = render_prompt(
                Path(__file__).resolve().parents[1] / "prompts" /
                "tutor_remediation.txt", transcript_text=transcript,
            )
            import json
            response = call_ai_client(
                ai_client, prompt=prompt + "\nCâu sai: " +
                json.dumps(incorrect_answers, ensure_ascii=False),
                transcript_text=transcript, transcript_methods=(),
            )
            result = parse_json_response(response)
            if (not isinstance(result, dict) or
                not isinstance(result.get("explanation"), str) or
                not result["explanation"].strip() or
                not isinstance(result.get("practice_questions"), list) or
                not result["practice_questions"]):
                raise ValueError("Invalid tutor response.")
            for question in result["practice_questions"]:
                if (not isinstance(question, dict) or
                    not isinstance(question.get("question"), str) or
                    not question["question"].strip() or
                    not isinstance(question.get("options"), list) or
                    len(question["options"]) < 2 or
                    question.get("correct_answer") not in question["options"] or
                    not isinstance(question.get("explanation"), str)):
                    raise ValueError("Invalid practice question.")
            return result
        except (RuntimeError, ValueError, TimeoutError, ConnectionError,
                OSError) as exc:
            if not allow_fallback:
                raise
            logger.warning("Tutor fallback: %s", type(exc).__name__)
    elif not allow_fallback:
        raise RuntimeError("An AI client is required.")
    logger.warning("Tutor source=original questions")
    return {
        "explanation": "Hãy xem lại nội dung bài giảng và thử lại các câu sai.",
        "practice_questions": [
            {key: item[key] for key in
             ("question", "options", "correct_answer", "explanation")}
            for item in incorrect_answers
        ],
    }
