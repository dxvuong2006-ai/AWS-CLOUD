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
    """Parse response and return schema-valid concept dictionaries."""
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
    """Return heuristic concepts grounded in non-empty transcript_text."""
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
