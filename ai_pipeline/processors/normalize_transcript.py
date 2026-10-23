import json
import re
from pathlib import Path
from typing import Any


_WHITESPACE_RE = re.compile(r"\s+")
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


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def _to_timestamp(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_segments(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, str):
        text = _clean_text(data)
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
            text = _clean_text(item)
            if text:
                segments.append({"text": text})
            continue
        if not isinstance(item, dict):
            continue

        text = _clean_text(item.get("text"))
        if not text:
            continue

        segment = {"text": text}
        start = _to_timestamp(item.get("start", item.get("start_time")))
        end = _to_timestamp(item.get("end", item.get("end_time")))
        if start is not None and end is not None:
            segment["start"] = start
            segment["end"] = end
        segments.append(segment)
    return segments


def _detect_language(text: str, declared_language: Any = None) -> str:
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


def normalize_transcript(raw_data: dict | list | str) -> dict:
    """Normalize transcript text and retain segments with valid timestamps."""
    data = raw_data
    if isinstance(raw_data, str):
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            data = raw_data

    declared_language = data.get("language") if isinstance(data, dict) else None
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


if __name__ == "__main__":
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "transcript_sample.json"
    )
    if fixture_path.exists():
        with fixture_path.open(encoding="utf-8") as fixture_file:
            transcript_data = json.load(fixture_file)
        normalized = normalize_transcript(transcript_data)
        print(normalized["word_count"])
    else:
        print(f"Transcript fixture not found: {fixture_path}")
