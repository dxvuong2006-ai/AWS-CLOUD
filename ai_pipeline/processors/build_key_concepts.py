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
        validate_schema,
    )
else:
    from _common import (
        AIClientError,
        call_ai_client,
        clean_text,
        extract_definition_concepts,
        parse_json_response,
        render_prompt,
        validate_schema,
    )


_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "key_concepts.txt"
)
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "summary.schema.json"
)
logger = logging.getLogger(__name__)


def validate_key_concepts(result: Any) -> list[dict[str, str]]:
    """Chuẩn hóa danh sách thuật ngữ và định nghĩa.

    Args:
        result: Danh sách khái niệm cần kiểm tra.

    Returns:
        Danh sách cặp term/definition đã làm sạch.

    Raises:
        ValueError: Danh sách rỗng, sai kiểu hoặc có trường nội dung rỗng.
    """
    if not isinstance(result, list):
        raise ValueError("AI response must contain a key_concepts list.")

    concepts = []
    for item in result:
        if not isinstance(item, dict):
            raise ValueError("Each key concept must be an object.")
        term = clean_text(item.get("term"))
        definition = clean_text(item.get("definition"))
        if not term or not definition:
            raise ValueError(
                "Each key concept needs a non-empty term and definition."
            )
        concepts.append({"term": term, "definition": definition})

    if not concepts:
        raise ValueError("AI response must contain at least one key concept.")
    return concepts


def _validate_concepts(response: Any) -> list[dict[str, str]]:
    """Phân tích và kiểm tra phản hồi khái niệm của AI.

    Args:
        response: Phản hồi AI cần phân tích và chuẩn hóa.

    Returns:
        Danh sách khái niệm phù hợp với định nghĩa trong schema summary.

    Raises:
        ValueError: JSON hoặc danh sách khái niệm không hợp lệ.
    """
    response = parse_json_response(response)
    result = (
        response.get("key_concepts")
        if isinstance(response, dict)
        else response
    )
    concepts = validate_key_concepts(result)
    validate_schema(
        {
            "title": "Concept validation",
            "summary": "Concept extraction result.",
            "key_concepts": concepts,
        },
        _SCHEMA_PATH,
    )
    return concepts


def _fallback_concepts(transcript_text: str) -> list[dict[str, str]]:
    """Trích xuất khái niệm dự phòng từ transcript.

    Args:
        transcript_text: Nội dung transcript làm nguồn xử lý bài giảng.

    Returns:
        Danh sách khái niệm theo mẫu câu hoặc một mục Ý chính.

    Raises:
        ValueError: Transcript không có nội dung để trích xuất.
    """
    concepts = extract_definition_concepts(transcript_text)
    if concepts:
        return concepts

    definition = clean_text(transcript_text)
    if not definition:
        raise ValueError("Cannot extract concepts from empty text.")
    return [{"term": "Ý chính", "definition": definition}]


def build_key_concepts(
    transcript_text: str,
    ai_client: Any = None,
    *,
    allow_fallback: bool = True,
) -> list[dict[str, str]]:
    """Tạo danh sách khái niệm với chính sách dự phòng tương thích.

    Mặc định cho phép heuristic khi thiếu client, thiếu chỉ dẫn hoặc gặp
    lỗi AI được hỗ trợ và ghi cảnh báo nguồn dữ liệu. allow_fallback=False
    bật chế độ nghiêm ngặt. Lỗi lập trình được ném lại.

    Args:
        transcript_text: Nội dung transcript làm nguồn xử lý bài giảng.
        ai_client: Đối tượng gọi AI; None để áp dụng chính sách dự phòng.
        allow_fallback: Cho phép kết quả dự phòng; mặc định True để tương
            thích.

    Returns:
        Danh sách term/definition đã kiểm tra, giữ nguyên hợp đồng đầu ra.

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
                    transcript_methods=(
                        "extract_key_concepts", "generate_key_concepts"
                    ),
                )
            except (AIClientError, TimeoutError, ConnectionError) as exc:
                if not allow_fallback:
                    raise AIClientError("AI request failed.") from exc
                reason = f"AI client failure: {type(exc).__name__}"
            else:
                try:
                    return _validate_concepts(response)
                except ValueError as exc:
                    if not allow_fallback:
                        raise
                    reason = f"invalid AI response: {exc}"

    logger.warning("build_key_concepts source=heuristic; reason=%s", reason)
    return _validate_concepts(_fallback_concepts(transcript_text))
