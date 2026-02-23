from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "data"
ALLOWED_PHASES = {"opening", "middlegame", "endgame"}


def load_yaml_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    output: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            output.append(item)
    return output


def as_text(value: Any) -> str | None:
    if isinstance(value, str):
        parsed = value.strip()
        return parsed or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def normalize_phase(value: Any, *, default: str) -> str:
    parsed = as_text(value)
    if parsed is None:
        return default
    normalized = parsed.lower()
    if normalized in ALLOWED_PHASES:
        return normalized
    return default


def normalize_tags(value: Any, *, defaults: tuple[str, ...] = ()) -> tuple[str, ...]:
    tags: list[str] = []
    if isinstance(value, list):
        for item in value:
            parsed = as_text(item)
            if parsed:
                token = parsed.lower().replace(" ", "_")
                if token not in tags:
                    tags.append(token)
    for default in defaults:
        normalized = default.lower().replace(" ", "_")
        if normalized and normalized not in tags:
            tags.append(normalized)
    return tuple(tags)


def build_chunk_id(
    *,
    source: str,
    index: int,
    explicit_id: Any = None,
    title: str | None = None,
    extra: str | None = None,
) -> str:
    parsed = as_text(explicit_id)
    if parsed:
        return parsed.lower().replace(" ", "-").replace("/", "-")

    payload_parts = [source, title or "", extra or "", str(index)]
    payload = "|".join(payload_parts).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:10]
    return f"{source}-{index + 1:03d}-{digest}"
