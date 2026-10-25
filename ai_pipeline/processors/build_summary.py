import json
import logging
from pathlib import Path
from typing import Any

if __package__:
    from ._common import (
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
    lower_sentence = sentence.lower()
    score = min(len(sentence.split()), 30)
    score += sum(term in lower_sentence for term in _IMPORTANT_TERMS) * 4
    if ":" in sentence or " - " in sentence:
        score += 2
    return score


def _fallback_summary(transcript_text: str) -> dict:
    sentences = split_sentences(transcript_text)

    if not sentences:
        title = "Tóm tắt bài giảng"
        summary = "Không có nội dung transcript để tóm tắt."
        concepts = [
            {
                "term": "Transcript",
                "definition": "Không có nội dung transcript được cung cấp.",
            }
        ]
    else:
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


def build_summary(transcript_text: str, ai_client=None) -> dict:
    (
        "Build a Draft-07-valid summary, using transcript extraction "
        "as fallback."
    )
    if ai_client is not None:
        try:
            prompt = render_prompt(
                _PROMPT_PATH,
                transcript_text=transcript_text,
            )
            response = call_ai_client(
                ai_client,
                prompt=prompt,
                transcript_text=transcript_text,
                transcript_methods=("generate_summary",),
            )
            return _validate_summary(response)
        except Exception as exc:
            logger.warning(
                "AI summary generation failed; using fallback: %s", exc
            )

    return _fallback_summary(transcript_text)


if __name__ == "__main__":
    if __package__:
        from ai_pipeline.processors.normalize_transcript import (
            normalize_transcript,
        )
    else:
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
                build_summary(normalized["full_text"]),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Transcript fixture not found: {transcript_path}")
