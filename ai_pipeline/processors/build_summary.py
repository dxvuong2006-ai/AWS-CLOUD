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


def _sentence_score(sentence: str) -> int:
    """Return a heuristic importance score for the supplied sentence."""
    lower_sentence = sentence.lower()
    score = min(len(sentence.split()), 30)
    score += sum(term in lower_sentence for term in _IMPORTANT_TERMS) * 4
    if ":" in sentence or " - " in sentence:
        score += 2
    return score


def _fallback_summary(transcript_text: str) -> dict:
    """Return a schema-valid extractive summary of transcript_text."""
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


def _validate_summary(response: Any) -> dict:
    """Parse response and return normalized summary fields or raise."""
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


def build_summary(
    transcript_text: str,
    ai_client: Any = None,
    *,
    allow_fallback: bool = True,
) -> dict:
    """Return validated content, allowing legacy heuristic fallback by default.

    transcript_text supplies the content; ai_client optionally generates it.
    Missing clients/prompts, declared AI failures and invalid responses may
    use heuristics with a warning. Set allow_fallback=False for strict mode.
    Output fields stay unchanged. Empty transcripts and programming errors
    propagate; adapters should wrap provider failures in AIClientError.
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
