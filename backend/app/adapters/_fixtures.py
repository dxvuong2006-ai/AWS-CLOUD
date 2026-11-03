import json
from pathlib import Path
from typing import Any


def _find_fixture_directory() -> Path:
    for parent in Path(__file__).resolve().parents:
        fixture_directory = parent / "ai_pipeline" / "fixtures"
        if fixture_directory.is_dir():
            return fixture_directory
    raise FileNotFoundError(
        "Could not locate the repository's ai_pipeline/fixtures directory."
    )


def load_json_fixture(filename: str) -> Any:
    fixture_path = _find_fixture_directory() / filename
    try:
        with fixture_path.open(encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Fixture contains invalid JSON: {fixture_path}") from exc
