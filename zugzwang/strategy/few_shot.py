from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from zugzwang.strategy.phase import normalize_phase

_BUILTIN_DIR = Path(__file__).resolve().parents[2] / "data" / "few_shot"
_ALLOWED_SOURCES = {"builtin", "config"}
_ALLOWED_PHASE_KEYS = {"opening", "middlegame", "endgame", "default"}


@dataclass(frozen=True)
class FewShotRenderResult:
    block: str | None
    example_count: int
    source: str


def render_few_shot_block(strategy_config: dict[str, Any], phase: str) -> str | None:
    return render_few_shot_block_with_metadata(strategy_config=strategy_config, phase=phase).block


def render_few_shot_block_with_metadata(
    strategy_config: dict[str, Any],
    phase: str,
) -> FewShotRenderResult:
    few_shot_cfg = strategy_config.get("few_shot", {})
    if not isinstance(few_shot_cfg, dict):
        return FewShotRenderResult(block=None, example_count=0, source="builtin")
    source = _resolve_source(few_shot_cfg)
    if not bool(few_shot_cfg.get("enabled", False)):
        return FewShotRenderResult(block=None, example_count=0, source=source)

    max_examples = _safe_positive_int(few_shot_cfg.get("max_examples"), default=0)
    if max_examples <= 0:
        return FewShotRenderResult(block=None, example_count=0, source=source)

    by_phase = load_few_shot_library(few_shot_cfg)
    if not by_phase:
        return FewShotRenderResult(block=None, example_count=0, source=source)

    normalized_phase = normalize_phase(phase)
    entries = by_phase.get(normalized_phase)
    if entries is None:
        entries = by_phase.get("default", [])
    if not isinstance(entries, list):
        return FewShotRenderResult(block=None, example_count=0, source=source)

    rendered: list[str] = []
    for entry in entries:
        if len(rendered) >= max_examples:
            break
        maybe_example = _render_example(entry, len(rendered) + 1)
        if maybe_example:
            rendered.append(maybe_example)

    if not rendered:
        return FewShotRenderResult(block=None, example_count=0, source=source)

    return FewShotRenderResult(
        block="\n\n".join(["Few-shot examples:", *rendered]),
        example_count=len(rendered),
        source=source,
    )


def load_few_shot_library(few_shot_cfg: dict[str, Any]) -> dict[str, list[Any]]:
    if not isinstance(few_shot_cfg, dict):
        return {}

    source = _resolve_source(few_shot_cfg)
    if source == "config":
        return _normalize_by_phase(few_shot_cfg.get("by_phase"))

    builtin = _load_builtin_library()
    if builtin:
        return builtin

    # Defensive fallback for environments without builtin data files.
    return _normalize_by_phase(few_shot_cfg.get("by_phase"))


def _resolve_source(few_shot_cfg: dict[str, Any]) -> str:
    source = few_shot_cfg.get("source")
    if isinstance(source, str):
        normalized = source.strip().lower()
        if normalized in _ALLOWED_SOURCES:
            return normalized

    # Backward compatibility for older configs that only provided by_phase inline.
    by_phase = few_shot_cfg.get("by_phase")
    if isinstance(by_phase, dict) and by_phase:
        return "config"
    return "builtin"


def _normalize_by_phase(raw: Any) -> dict[str, list[Any]]:
    if not isinstance(raw, dict):
        return {}

    output: dict[str, list[Any]] = {}
    for phase_key, entries in raw.items():
        if not isinstance(phase_key, str):
            continue
        normalized_key = _normalize_phase_key(phase_key)
        parsed_entries = _extract_examples(entries, normalized_key)
        if parsed_entries:
            output[normalized_key] = parsed_entries
    return output


@lru_cache(maxsize=1)
def _load_builtin_library_cached() -> dict[str, list[Any]]:
    if not _BUILTIN_DIR.exists():
        return {}

    library: dict[str, list[Any]] = {}
    for file_path in sorted(_BUILTIN_DIR.glob("*.yml")) + sorted(_BUILTIN_DIR.glob("*.yaml")):
        phase_key = _normalize_phase_key(file_path.stem)
        payload = _read_yaml_payload(file_path)
        entries = _extract_examples(payload, phase_key)
        if entries:
            library[phase_key] = entries
    return library


def _load_builtin_library() -> dict[str, list[Any]]:
    return copy.deepcopy(_load_builtin_library_cached())


def _read_yaml_payload(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_examples(payload: Any, phase_key: str) -> list[Any]:
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    examples = payload.get("examples")
    if isinstance(examples, list):
        return examples

    direct_phase_examples = payload.get(phase_key)
    if isinstance(direct_phase_examples, list):
        return direct_phase_examples

    by_phase = payload.get("by_phase")
    if isinstance(by_phase, dict):
        nested = by_phase.get(phase_key)
        if isinstance(nested, list):
            return nested

    return []


def _normalize_phase_key(raw: str) -> str:
    cleaned = raw.strip().lower()
    if cleaned in _ALLOWED_PHASE_KEYS:
        return cleaned
    return normalize_phase(cleaned)


def _safe_positive_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value > 0 else default
    if isinstance(value, float):
        casted = int(value)
        return casted if casted > 0 else default
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            casted = int(stripped)
            return casted if casted > 0 else default
    return default


def _render_example(entry: Any, index: int) -> str | None:
    if isinstance(entry, str):
        sample = entry.strip()
        if not sample:
            return None
        return f"Example {index}:\n{sample}"

    if not isinstance(entry, dict):
        return None

    input_text = entry.get("input")
    output_text = entry.get("output")

    if not isinstance(input_text, str) or not input_text.strip():
        fen = entry.get("fen")
        if isinstance(fen, str) and fen.strip():
            input_text = f"FEN: {fen.strip()}"

    if not isinstance(output_text, str) or not output_text.strip():
        move_uci = entry.get("move_uci")
        if isinstance(move_uci, str) and move_uci.strip():
            output_text = move_uci.strip()

    if not isinstance(input_text, str) or not input_text.strip():
        return None
    if not isinstance(output_text, str) or not output_text.strip():
        return None

    note = entry.get("note")
    note_line = f"\nNote: {note.strip()}" if isinstance(note, str) and note.strip() else ""
    return f"Example {index}:\nInput:\n{input_text.strip()}\nOutput:\n{output_text.strip()}{note_line}"
