#tóm tắt nội dung bài giảng
import logging
from pathlib import Path
from typing import Any

if __package__:
    from ._common import (
        AIClientError,
        call_ai_client,
        clean_text,
        extract_definition_concepts,
        parse_json_response,
        render_prompt,
        split_sentences,
        validate_schema,
    )
    from .build_key_concepts import validate_key_concepts
else:
    from _common import (
        AIClientError,
        call_ai_client,
        clean_text,
        extract_definition_concepts,
        parse_json_response,
        render_prompt,
        split_sentences,
        validate_schema,
    )
    from build_key_concepts import validate_key_concepts


_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "summary.txt"
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "summary.schema.json"
)
_IMPORTANT_TERMS = (
    "là",
    "bao gồm",
    "cung cấp",
    "cho phép",
    "giúp",
    "được gọi là",
    "mô hình",
    "khả năng",
    "therefore",
    "is",
    "are",
    "allows",
    "provides",
    "means",
)
logger = logging.getLogger(__name__)

#Thuật toán chấm điểm câu theo quy tắc
def _sentence_score(sentence: str) -> int:
    """Tính điểm quan trọng của một câu theo quy tắc.

    Args:
        sentence: Câu văn cần tính điểm quan trọng.

    Returns:
        Điểm dựa trên độ dài, từ khóa và dấu phân cách.
    """
    lower_sentence = sentence.lower()
    score = min(len(sentence.split()), 30)
    score += sum(term in lower_sentence for term in _IMPORTANT_TERMS) * 4
    if ":" in sentence or " - " in sentence:
        score += 2
    return score

#Bộ sinh tóm tắt dự phòng
def _fallback_summary(transcript_text: str) -> dict:
    """Tạo bản tóm tắt dự phòng từ các câu trong transcript.

    Args:
        transcript_text: Nội dung transcript làm nguồn xử lý bài giảng.

    Returns:
        Đối tượng summary hợp schema, giữ nội dung trích từ transcript.

    Raises:
        ValueError: Văn bản rỗng hoặc kết quả không thỏa mãn schema.
    """
    sentences = split_sentences(transcript_text)

    if not sentences:
        raise ValueError("Cannot summarize empty text.")

    ranked = sorted(
        enumerate(sentences),
        key=lambda item: (-_sentence_score(item[1]), item[0]),
    )
    selected = sorted(ranked[:3])
    important_sentences = [sentence for _, sentence in selected]

    title = sentences[0].rstrip(".!?。！？")
    title_words = title.split()
    if len(title_words) > 12:
        title = " ".join(title_words[:12]).rstrip(" ,:;-") + "..."

    summary = " ".join(important_sentences)
    concepts = extract_definition_concepts(summary)
    if not concepts:
        concepts = [
            {
                "term": "Ý chính",
                "definition": important_sentences[0],
            }
        ]

    return validate_schema(
        {
            "title": title or "Tóm tắt bài giảng",
            "summary": summary,
            "key_concepts": concepts,
        },
        _SCHEMA_PATH,
    )

#Thẩm định và đóng gói kết quả từ AI
def _validate_summary(response: Any) -> dict:
    """Chuẩn hóa và kiểm tra phản hồi tóm tắt của AI.

    Args:
        response: Phản hồi AI cần phân tích và chuẩn hóa.

    Returns:
        Đối tượng gồm title, summary và key_concepts hợp lệ.

    Raises:
        ValueError: Phản hồi JSON hoặc các trường nội dung không hợp lệ.
    """
    result = parse_json_response(response)
    if not isinstance(result, dict):
        raise ValueError("AI summary must be a JSON object.")

    title = clean_text(result.get("title"))
    summary = clean_text(result.get("summary"))
    concepts = validate_key_concepts(result.get("key_concepts"))

    if not title or not summary:
        raise ValueError("AI summary title and summary must be non-empty.")
    return validate_schema(
        {
            "title": title,
            "summary": summary,
            "key_concepts": concepts,
        },
        _SCHEMA_PATH,
    )

#Hàm điều phối chính và xử lý lỗi phân nhánh
def build_summary(
    transcript_text: str,
    ai_client: Any = None,
    *,
    allow_fallback: bool = True,
) -> dict:
    """Tạo tóm tắt bài giảng với chính sách dự phòng tương thích.

    Mặc định cho phép heuristic khi thiếu client, thiếu chỉ dẫn hoặc gặp
    lỗi AI được hỗ trợ và ghi cảnh báo nguồn dữ liệu. allow_fallback=False
    bật chế độ nghiêm ngặt. Lỗi lập trình được ném lại.

    Args:
        transcript_text: Nội dung transcript làm nguồn xử lý bài giảng.
        ai_client: Đối tượng gọi AI; None để áp dụng chính sách dự phòng.
        allow_fallback: Cho phép kết quả dự phòng; mặc định True để tương
            thích.

    Returns:
        Đối tượng tóm tắt hợp schema, không thêm trường metadata.

    Raises:
        ValueError: Transcript rỗng hoặc phản hồi sai khi tắt dự phòng.
        AIClientError: Thiếu client hoặc lỗi AI khi tắt dự phòng.
        FileNotFoundError: Thiếu tệp chỉ dẫn khi tắt dự phòng.
    """
    if not clean_text(transcript_text):
        raise ValueError("transcript_text must be a non-empty string.")
    if ai_client is None:
        if not allow_fallback:
            raise AIClientError("An AI client is required in strict mode.")
        reason = "no AI client configured"
    else:
        try:
            prompt = render_prompt(
                _PROMPT_PATH,
                transcript_text=transcript_text,
            )
        except FileNotFoundError as exc:
            if not allow_fallback:
                raise
            reason = f"prompt unavailable: {exc}"
        else:
            try:
                response = call_ai_client(
                    ai_client,
                    prompt=prompt,
                    transcript_text=transcript_text,
                    transcript_methods=("generate_summary",),
                )
            except (AIClientError, TimeoutError, ConnectionError) as exc:
                if not allow_fallback:
                    raise AIClientError("AI request failed.") from exc
                reason = f"AI client failure: {type(exc).__name__}"
            else:
                try:
                    return _validate_summary(response)
                except ValueError as exc:
                    if not allow_fallback:
                        raise
                    reason = f"invalid AI response: {exc}"

    logger.warning("build_summary source=heuristic; reason=%s", reason)
    return _fallback_summary(transcript_text)
