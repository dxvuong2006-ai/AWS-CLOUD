"""Tạo học liệu nháp từ transcript S3; không tự ghi trạng thái bài học."""

import json
import logging
from urllib.parse import urlparse

import boto3

from ai_pipeline.processors.normalize_transcript import normalize_transcript
from app.adapters.ai.bedrock_ai import AWS_FAILURES, BedrockAIAdapter
from ai_pipeline.processors._common import parse_json_response

logger = logging.getLogger(__name__)



def build_flashcards(concepts, transcript, ai):
    """Sinh điểm ứng dụng riêng cho từng khái niệm, có dự phòng rõ ràng."""
    fallback = [
        {"term": item["term"], "definition": item["definition"],
         "key_takeaway": "Ứng dụng cốt lõi: " + item["definition"]}
        for item in concepts
    ]
    if getattr(ai, "used_fallback", False):
        return fallback
    prompt = (
        "Dựa vào bài giảng, tạo JSON object với trường cards là danh sách; "
        "mỗi phần tử chỉ gồm term và key_takeaway. Giữ nguyên từng term. "
        "key_takeaway nêu ứng dụng thực tiễn bằng 1-2 câu ngắn, "
        "không lặp nguyên văn định nghĩa. Không thêm khái niệm.\n"
        "Bài giảng: " + transcript + "\nKhái niệm: " +
        json.dumps(concepts, ensure_ascii=False)
    )
    try:
        result = parse_json_response(ai._invoke(prompt))
        cards = result["cards"]
        if not isinstance(cards, list) or len(cards) != len(concepts):
            raise ValueError("Invalid flashcards count.")
        by_term = {}
        for card in cards:
            term, takeaway = card["term"], card["key_takeaway"]
            if (not isinstance(term, str) or term in by_term or
                not isinstance(takeaway, str) or not takeaway.strip()):
                raise ValueError("Invalid flashcard.")
            by_term[term] = takeaway.strip()
        if set(by_term) != {item["term"] for item in concepts}:
            raise ValueError("Flashcard terms do not match.")
        if any(by_term[item["term"]].casefold() == item["definition"].strip().casefold()
               for item in concepts):
            raise ValueError("Key takeaway repeats definition.")
        return [{**item, "key_takeaway": by_term[item["term"]]} for item in concepts]
    except (*AWS_FAILURES, ValueError, KeyError, TypeError) as exc:
        logger.warning("Flashcards source=heuristic; reason=%s", type(exc).__name__)
        return fallback


def lambda_handler(event, context):
    """Đọc transcript từ S3 và trả dữ liệu chờ duyệt.

    Args:
        event: lesson_id và transcript_text hoặc s3_transcript_uri.
        context: Ngữ cảnh Lambda.

    Returns:
        Học liệu nháp; review_content khớp DraftContent. Chưa ghi DB.
    """
    if event.get("transcript_text"):
        raw = event["transcript_text"]
    else:
        uri = urlparse(event.get("s3_transcript_uri") or event.get("transcript_uri", ""))
        if uri.scheme != "s3" or not uri.netloc or not uri.path.strip("/"):
            raise ValueError("Provide transcript_text or an s3:// transcript URI.")
        body = boto3.client("s3").get_object(
            Bucket=uri.netloc, Key=uri.path.lstrip("/")
        )["Body"]
        try:
            raw = json.loads(body.read())
        finally:
            body.close()
    # Amazon Transcribe stores word timestamps in results.items.
    if isinstance(raw, dict) and isinstance(raw.get("results"), dict):
        items = raw["results"].get("items", [])
        raw = {"segments": [
            {"text": item["alternatives"][0]["content"],
             "start": item.get("start_time"), "end": item.get("end_time")}
            for item in items
            if item.get("type") == "pronunciation" and item.get("alternatives")
        ]}
    transcript = normalize_transcript(raw)
    text = transcript["full_text"]
    if not text:
        raise ValueError("Transcript is empty.")
    ai = BedrockAIAdapter(allow_fallback=False)
    summary = ai.generate_summary(text)
    concepts = ai.extract_key_concepts(text)
    quiz = ai.generate_quiz(text)
    return {
        "lesson_id": event["lesson_id"], "status": "REVIEW_REQUIRED",
        "transcript": transcript,
        "review_content": {
            "title": summary["title"], "summary": summary["summary"],
            "key_concepts": concepts, "quiz_title": summary["title"],
            "questions": quiz["questions"],
        },
        "flashcards": build_flashcards(concepts, text, ai),
    }
