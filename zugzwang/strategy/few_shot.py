from __future__ import annotations

from typing import Any

from zugzwang.strategy.phase import normalize_phase


def render_few_shot_block(strategy_config: dict[str, Any], phase: str) -> str | None:
    few_shot_cfg = strategy_config.get("few_shot", {})
    if not isinstance(few_shot_cfg, dict):
        return None
    if not bool(few_shot_cfg.get("enabled", False)):
        return None

    max_examples = int(few_shot_cfg.get("max_examples", 0))
    if max_examples <= 0:
        return None

    by_phase = few_shot_cfg.get("by_phase", {})
    if not isinstance(by_phase, dict):
        return None

    normalized_phase = normalize_phase(phase)
    entries = by_phase.get(normalized_phase)
    if entries is None:
        entries = by_phase.get("default", [])
    if not isinstance(entries, list):
        return None

    rendered: list[str] = []
    for index, entry in enumerate(entries[:max_examples], start=1):
        maybe_example = _render_example(entry, index)
        if maybe_example:
            rendered.append(maybe_example)

    if not rendered:
        return None

    return "\n\n".join(["Few-shot examples:", *rendered])


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
