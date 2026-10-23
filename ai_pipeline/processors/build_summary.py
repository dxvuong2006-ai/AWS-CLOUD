import json
import logging
import re
from pathlib import Path
from typing import Any


_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "summary.txt"
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")
_WHITESPACE_RE = re.compile(r"\s+")
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


def _clean_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _split_sentences(transcript_text: str) -> list[str]:
    return [
        sentence
        for sentence in (
            _clean_text(part) for part in _SENTENCE_SPLIT_RE.split(transcript_text)
        )
        if sentence
    ]


def _sentence_score(sentence: str) -> int:
    lower_sentence = sentence.lower()
    score = min(len(sentence.split()), 30)
    score += sum(term in lower_sentence for term in _IMPORTANT_TERMS) * 4
    if ":" in sentence or " - " in sentence:
        score += 2
    return score


def _concept_term(sentence: str, index: int) -> str:
    lower_sentence = sentence.lower()
    for marker in _IMPORTANT_TERMS:
        marker_index = lower_sentence.find(marker)
        if marker_index > 0:
            term = sentence[:marker_index].strip(" ,:;-")
            if term:
                return term[:80]

    words = sentence.split()
    if len(words) > 8:
        return " ".join(words[:6]).strip(" ,:;-") or f"Ý chính {index}"
    return f"Ý chính {index}"


def _fallback_summary(transcript_text: str) -> dict:
    sentences = _split_sentences(transcript_text)
    if not sentences and _clean_text(transcript_text):
        sentences = [_clean_text(transcript_text)]

    if not sentences:
        return {
            "title": "Tóm tắt bài giảng",
            "summary": "Không có nội dung transcript để tóm tắt.",
            "key_concepts": [
                {
                    "term": "Transcript",
                    "definition": "Không có nội dung transcript được cung cấp.",
                }
            ],
        }

    ranked_sentences = sorted(
        enumerate(sentences),
        key=lambda item: (-_sentence_score(item[1]), item[0]),
    )
    selected = sorted(ranked_sentences[: min(3, len(ranked_sentences))])
    important_sentences = [sentence for _, sentence in selected]
    title = sentences[0].rstrip(".!?。！？")
    title_words = title.split()
    if len(title_words) > 12:
        title = " ".join(title_words[:12]).rstrip(" ,:;-") + "..."

    concepts = [
        {
            "term": _concept_term(sentence, index),
            "definition": sentence,
        }
        for index, sentence in enumerate(important_sentences, start=1)
    ]
    return {
        "title": title or "Tóm tắt bài giảng",
        "summary": " ".join(important_sentences),
        "key_concepts": concepts,
    }


def _extract_client_text(response: Any) -> Any:
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


def _validate_summary(response: Any) -> dict:
    result = _extract_client_text(response)
    if not isinstance(result, dict):
        raise ValueError("AI summary must be a JSON object.")

    title = result.get("title")
    summary = result.get("summary")
    concepts = result.get("key_concepts")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("AI summary title must be a non-empty string.")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("AI summary text must be a non-empty string.")
    if not isinstance(concepts, list) or not concepts:
        raise ValueError("AI summary must contain at least one key concept.")

    validated_concepts = []
    for concept in concepts:
        if not isinstance(concept, dict):
            raise ValueError("Each key concept must be a JSON object.")
        term = concept.get("term")
        definition = concept.get("definition")
        if (
            not isinstance(term, str)
            or not term.strip()
            or not isinstance(definition, str)
            or not definition.strip()
        ):
            raise ValueError("Key concepts require non-empty term and definition.")
        validated_concepts.append(
            {"term": term.strip(), "definition": definition.strip()}
        )

    return {
        "title": title.strip(),
        "summary": summary.strip(),
        "key_concepts": validated_concepts,
    }


def _generate_with_client(ai_client: Any, transcript_text: str, prompt: str) -> Any:
    generate_summary = getattr(ai_client, "generate_summary", None)
    if callable(generate_summary):
        return generate_summary(transcript_text)

    generate = getattr(ai_client, "generate", None)
    if callable(generate):
        return generate(prompt)

    invoke = getattr(ai_client, "invoke", None)
    if callable(invoke):
        return invoke(prompt)

    if callable(ai_client):
        return ai_client(prompt)

    raise TypeError(
        "ai_client must provide generate_summary, generate, invoke, or __call__."
    )


def build_summary(transcript_text: str, ai_client=None) -> dict:
    """Build a schema-compatible summary, falling back to transcript extraction."""
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.replace("{{transcript}}", transcript_text)

    if ai_client is not None:
        try:
            response = _generate_with_client(ai_client, transcript_text, prompt)
            return _validate_summary(response)
        except Exception as exc:
            logger.warning("AI summary generation failed; using fallback: %s", exc)

    return _fallback_summary(transcript_text)


if __name__ == "__main__":
    from normalize_transcript import normalize_transcript

    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"
    transcript_path = fixtures_dir / "transcript_sample.json"
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
