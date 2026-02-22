from __future__ import annotations

from typing import Any

from zugzwang.core.models import GameState
from zugzwang.strategy.few_shot import render_few_shot_block
from zugzwang.strategy.formats import board_context_lines
from zugzwang.strategy.phase import normalize_phase


DEFAULT_COMPRESSION_ORDER = ["history", "legal_moves", "few_shot"]


def build_direct_prompt(
    game_state: GameState,
    strategy_config: dict[str, Any],
    retry_feedback: str | None = None,
) -> str:
    board_format = str(strategy_config.get("board_format", "fen"))
    include_legal = bool(strategy_config.get("provide_legal_moves", True))
    include_history = bool(strategy_config.get("provide_history", True))
    history_plies = int(strategy_config.get("history_plies", 8))

    phase = normalize_phase(game_state.phase)

    base_lines = [
        "You are a chess assistant playing one move.",
        "Return exactly one legal move in UCI format.",
        "Do not include explanation.",
        f"Phase: {phase}",
        f"Side to move: {game_state.active_color}",
        *board_context_lines(game_state.fen, board_format),
    ]

    optional_blocks: dict[str, str] = {}

    few_shot = render_few_shot_block(strategy_config, phase=phase)
    if few_shot:
        optional_blocks["few_shot"] = few_shot

    if include_history:
        tail = game_state.history_uci[-history_plies:] if history_plies > 0 else []
        history_line = ", ".join(tail) if tail else "(none)"
        optional_blocks["history"] = (
            f"Previous moves (UCI, last {history_plies} plies): {history_line}"
        )

    if include_legal:
        optional_blocks["legal_moves"] = f"Legal moves (UCI): {', '.join(game_state.legal_moves_uci)}"

    if retry_feedback:
        optional_blocks["retry_feedback"] = f"Validation feedback: {retry_feedback}"

    context_cfg = strategy_config.get("context", {})
    max_prompt_chars = _read_positive_int(context_cfg, "max_prompt_chars")
    compression_order = _read_compression_order(context_cfg)

    lines, dropped = _compress_prompt(
        base_lines=base_lines,
        optional_blocks=optional_blocks,
        compression_order=compression_order,
        max_prompt_chars=max_prompt_chars,
    )

    prompt = "\n".join(lines)
    if dropped:
        prompt = "\n".join([prompt, f"Context compression: dropped {', '.join(dropped)}."])

    if max_prompt_chars is not None and len(prompt) > max_prompt_chars:
        prompt = _truncate_prompt(prompt, max_prompt_chars)

    return prompt


def _compress_prompt(
    base_lines: list[str],
    optional_blocks: dict[str, str],
    compression_order: list[str],
    max_prompt_chars: int | None,
) -> tuple[list[str], list[str]]:
    current = dict(optional_blocks)
    dropped: list[str] = []

    lines = _join_blocks(base_lines, current)
    if max_prompt_chars is None or len("\n".join(lines)) <= max_prompt_chars:
        return lines, dropped

    for block_name in compression_order:
        if block_name == "retry_feedback":
            continue
        if block_name not in current:
            continue
        current.pop(block_name)
        dropped.append(block_name)
        lines = _join_blocks(base_lines, current)
        if len("\n".join(lines)) <= max_prompt_chars:
            return lines, dropped

    prompt = "\n".join(lines)
    if len(prompt) > max_prompt_chars:
        prompt = _truncate_prompt(prompt, max_prompt_chars)
    return prompt.splitlines(), dropped


def _join_blocks(base_lines: list[str], optional_blocks: dict[str, str]) -> list[str]:
    output = list(base_lines)
    for key in ("few_shot", "history", "legal_moves", "retry_feedback"):
        block = optional_blocks.get(key)
        if block:
            output.append(block)
    return output


def _read_positive_int(config: Any, key: str) -> int | None:
    if not isinstance(config, dict):
        return None
    value = config.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            casted = int(stripped)
            return casted if casted > 0 else None
    return None


def _read_compression_order(context_cfg: Any) -> list[str]:
    if not isinstance(context_cfg, dict):
        return list(DEFAULT_COMPRESSION_ORDER)
    raw_order = context_cfg.get("compression_order")
    if not isinstance(raw_order, list):
        return list(DEFAULT_COMPRESSION_ORDER)

    normalized: list[str] = []
    for item in raw_order:
        if not isinstance(item, str):
            continue
        key = item.strip().lower()
        if key in {"few_shot", "history", "legal_moves", "retry_feedback"} and key not in normalized:
            normalized.append(key)

    if not normalized:
        return list(DEFAULT_COMPRESSION_ORDER)
    return normalized


def _truncate_prompt(prompt: str, max_prompt_chars: int) -> str:
    marker = "\n[truncated]"
    if max_prompt_chars <= 0:
        return ""
    if len(prompt) <= max_prompt_chars:
        return prompt
    if max_prompt_chars <= len(marker):
        return prompt[:max_prompt_chars]
    head = prompt[: max_prompt_chars - len(marker)].rstrip()
    return f"{head}{marker}"
