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
        validate_schema,
    )
else:
    from _common import (
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
    """Normalize and validate concept fields shared by pipeline outputs."""
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
    concepts = extract_definition_concepts(transcript_text)
    if concepts:
        return concepts

    definition = clean_text(transcript_text)
    if not definition:
        definition = "Không có nội dung transcript để trích xuất khái niệm."
    return [{"term": "Ý chính", "definition": definition}]


def build_key_concepts(transcript_text: str, ai_client=None) -> list[dict]:
    """Extract Draft-07-valid concepts, falling back to transcript text."""
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
                transcript_methods=(
                    "extract_key_concepts",
                    "generate_key_concepts",
                ),
            )
            return _validate_concepts(response)
        except Exception as exc:
            logger.warning(
                "AI key concept extraction failed; using fallback: %s", exc
            )

    return _validate_concepts(_fallback_concepts(transcript_text))


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
                build_key_concepts(normalized["full_text"]),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Transcript fixture not found: {transcript_path}")
