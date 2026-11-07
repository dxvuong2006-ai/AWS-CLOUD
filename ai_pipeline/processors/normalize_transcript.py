#làm sách và chuẩn hoá văn bản thôi
import json
import math
import re
from typing import Any

if __package__:
    from ._common import clean_text
else:
    from _common import clean_text

_VIETNAMESE_RE = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
    r"óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)
_ENGLISH_WORDS = {
    "a",
    "about",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}

#Hàm chuẩn hóa mốc thời gian
def _to_timestamp(value: Any) -> float | None:
    """Chuyển giá trị thành mốc thời gian hợp lệ.

    Args:
        value: Giá trị cần chuẩn hóa hoặc chuyển đổi.

    Returns:
        Số thực hữu hạn không âm; None nếu không chuyển đổi được.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return timestamp if math.isfinite(timestamp) and timestamp >= 0 else None

#Hàm thu thập và bóc tách đoạn thoại
def _collect_segments(data: Any) -> list[dict[str, Any]]:
    """Thu thập các đoạn transcript từ dữ liệu lồng nhau.

    Args:
        data: Dữ liệu cần thu thập hoặc kiểm tra.

    Returns:
        Danh sách đoạn có văn bản sạch và cặp thời gian hợp lệ nếu có.
    """
    if isinstance(data, str):
        text = clean_text(data)
        return [{"text": text}] if text else []

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        nested = data.get("segments")
        if nested is None:
            nested = data.get("transcript")
        if isinstance(nested, (dict, list, str)):
            return _collect_segments(nested)
        if "text" in data:
            items = [data]
        else:
            return []
    else:
        return []

    segments = []
    for item in items:
        if isinstance(item, str):
            text = clean_text(item)
            if text:
                segments.append({"text": text})
            continue
        if not isinstance(item, dict):
            continue

        text = clean_text(item.get("text"))
        if not text:
            continue

        segment = {"text": text}
        start = _to_timestamp(item.get("start", item.get("start_time")))
        end = _to_timestamp(item.get("end", item.get("end_time")))
        if start is not None and end is not None and end >= start:
            segment["start"] = start
            segment["end"] = end
        segments.append(segment)
    return segments

#Hàm nhận diện ngôn ngữ
def _detect_language(text: str, declared_language: Any = None) -> str:
    """Xác định tiếng Việt hoặc tiếng Anh của transcript.

    Args:
        text: Văn bản đầu vào cần phân tích.
        declared_language: Mã ngôn ngữ được khai báo; None để nhận diện từ
            văn bản.

    Returns:
        Mã vi hoặc en theo khai báo hoặc quy tắc nhận diện.
    """
    if isinstance(declared_language, str):
        language = declared_language.strip().lower()
        if language in {"vi", "en"}:
            return language
        if language.startswith("vi"):
            return "vi"
        if language.startswith("en"):
            return "en"

    if _VIETNAMESE_RE.search(text):
        return "vi"

    words = re.findall(r"[a-z']+", text.lower())
    english_word_count = sum(word in _ENGLISH_WORDS for word in words)
    return "en" if words and english_word_count / len(words) >= 0.2 else "vi"

#Hàm điều phối chuẩn hóa chính
def normalize_transcript(raw_data: dict | list | str) -> dict:
    """Chuẩn hóa transcript và giữ các đoạn có thời gian hợp lệ.

    Chuỗi không giải mã được JSON được xử lý như văn bản. Đoạn có thời gian
    không hợp lệ vẫn đóng góp nội dung vào full_text.

    Args:
        raw_data: Transcript dạng đối tượng, danh sách hoặc chuỗi JSON/văn
            bản.

    Returns:
        Đối tượng gồm full_text, segments, word_count và language.
    """
    data = raw_data
    if isinstance(raw_data, str):
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            data = raw_data

    declared_language = (
        data.get("language") if isinstance(data, dict) else None
    )
    normalized_segments = _collect_segments(data)
    text_parts = [segment["text"] for segment in normalized_segments]
    full_text = " ".join(text_parts)
    timed_segments = [
        {
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"],
        }
        for segment in normalized_segments
        if "start" in segment and "end" in segment
    ]

    return {
        "full_text": full_text,
        "segments": timed_segments,
        "word_count": len(full_text.split()),
        "language": _detect_language(full_text, declared_language),
    }
