import json
import logging
import re
from pathlib import Path
from typing import Any


_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "key_concepts.txt"
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")
_WHITESPACE_RE = re.compile(r"\s+")
_DEFINITION_RE = re.compile(
    r"\b(?P<marker>defined\s+as|is|are)\b|"
    r"(?P<vi_marker>bao gồm|cung cấp|là|cho phép)",
    re.IGNORECASE,
)
_LEADING_FILLER_RE = re.compile(
    r"^(?:(?:mô hình|một|the|a|an)\s+)+",
    re.IGNORECASE,
)
logger = logging.getLogger(__name__)


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def _extract_response(response: Any) -> Any:
    if isinstance(response, (dict, list)):
        return response
    if isinstance(response, str):
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return response


def _validate_concepts(response: Any) -> list[dict[str, str]]:
    result = _extract_response(response)
    if isinstance(result, dict):
        result = result.get("key_concepts")
    if not isinstance(result, list) or not result:
        raise ValueError("AI response must contain a non-empty key_concepts list.")

    concepts = []
    for item in result:
        if not isinstance(item, dict):
            raise ValueError("Each key concept must be an object.")
        term = _clean_text(item.get("term"))
        definition = _clean_text(item.get("definition"))
        if not term or not definition:
            raise ValueError("Each key concept needs a non-empty term and definition.")
        concepts.append({"term": term, "definition": definition})
    return concepts


def _term_from_prefix(prefix: str) -> str:
    term = _LEADING_FILLER_RE.sub("", prefix.strip(" ,:;-"))
    words = term.split()
    if len(words) > 8:
        term = " ".join(words[-8:])
    return term.strip(" ,:;-")


def _fallback_concepts(transcript_text: str) -> list[dict[str, str]]:
    concepts = []
    seen_terms = set()
    for sentence in (
        _clean_text(part) for part in _SENTENCE_SPLIT_RE.split(transcript_text)
    ):
        if not sentence:
            continue

        match = _DEFINITION_RE.search(sentence)
        if match is None:
            continue

        marker = (match.group("marker") or match.group("vi_marker")).lower()
        prefix = sentence[: match.start()]
        if marker == "cung cấp" and prefix.rstrip().lower().endswith("nhà"):
            continue

        term = _term_from_prefix(sentence[: match.start()])
        if marker == "là" and term.lower().startswith("lợi ích"):
            described_term = sentence[match.end() :].split(":", 1)[0]
            term = _clean_text(described_term).rstrip(".!?。！？")
        if not term:
            continue
        normalized_term = term.casefold()
        if normalized_term in seen_terms:
            continue

        seen_terms.add(normalized_term)
        concepts.append({"term": term, "definition": sentence})

    if concepts:
        return concepts

    fallback_text = _clean_text(transcript_text)
    if not fallback_text:
        fallback_text = "Không có nội dung transcript để trích xuất khái niệm."
    return [{"term": "Ý chính", "definition": fallback_text}]


def _generate_with_client(ai_client: Any, transcript_text: str, prompt: str) -> Any:
    extract_key_concepts = getattr(ai_client, "extract_key_concepts", None)
    if callable(extract_key_concepts):
        return extract_key_concepts(transcript_text)

    generate_key_concepts = getattr(ai_client, "generate_key_concepts", None)
    if callable(generate_key_concepts):
        return generate_key_concepts(transcript_text)

    generate = getattr(ai_client, "generate", None)
    if callable(generate):
        return generate(prompt)

    invoke = getattr(ai_client, "invoke", None)
    if callable(invoke):
        return invoke(prompt)

    if callable(ai_client):
        return ai_client(prompt)

    raise TypeError(
        "ai_client must provide extract_key_concepts, generate, invoke, or __call__."
    )


def build_key_concepts(transcript_text: str, ai_client=None) -> list[dict]:
    """Extract schema-compatible key concepts, falling back to transcript rules."""
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = template.replace("{{transcript}}", transcript_text)
        if ai_client is not None:
            response = _generate_with_client(ai_client, transcript_text, prompt)
            return _validate_concepts(response)
    except Exception as exc:
        logger.warning("AI key concept extraction failed; using fallback: %s", exc)

    return _fallback_concepts(transcript_text)


if __name__ == "__main__":
    from normalize_transcript import normalize_transcript

    transcript_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "transcript_sample.json"
    )
    if transcript_path.exists():
        with transcript_path.open(encoding="utf-8") as transcript_file:
            transcript_data = json.load(transcript_file)
        normalized = normalize_transcript(transcript_data)
        print(
            json.dumps(
                build_key_concepts(normalized["full_text"]),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Transcript fixture not found: {transcript_path}")
