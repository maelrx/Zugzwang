from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from zugzwang.core.models import GameState
from zugzwang.knowledge.retriever import (
    DEFAULT_MAX_CHARS_PER_CHUNK,
    query as query_knowledge,
)
from zugzwang.strategy.few_shot import render_few_shot_block_with_metadata
from zugzwang.strategy.formats import board_context_lines
from zugzwang.strategy.phase import normalize_phase
from zugzwang.strategy.prompts import DEFAULT_PROMPT_ID, resolve_system_prompt


DEFAULT_COMPRESSION_ORDER = ["history", "rag", "legal_moves", "few_shot"]


@dataclass(frozen=True)
class PromptRetrievalTelemetry:
    enabled: bool
    hit_count: int
    latency_ms: int
    sources: list[str] = field(default_factory=list)
    phase: str | None = None


@dataclass(frozen=True)
class PromptBuildResult:
    prompt: str
    dropped_blocks: list[str]
    retrieval: PromptRetrievalTelemetry
    few_shot_examples_injected: int = 0
    system_content: str | None = None
    user_content: str = ""
    prompt_id_requested: str = DEFAULT_PROMPT_ID
    prompt_id_effective: str = DEFAULT_PROMPT_ID
    prompt_label: str = "Default Assistant"


def build_direct_prompt(
    game_state: GameState,
    strategy_config: dict[str, Any],
    retry_feedback: str | None = None,
) -> str:
    return build_direct_prompt_with_metadata(
        game_state=game_state,
        strategy_config=strategy_config,
        retry_feedback=retry_feedback,
    ).prompt


def build_direct_prompt_with_metadata(
    game_state: GameState,
    strategy_config: dict[str, Any],
    retry_feedback: str | None = None,
) -> PromptBuildResult:
    board_format = str(strategy_config.get("board_format", "fen"))
    include_legal = bool(strategy_config.get("provide_legal_moves", True))
    include_history = bool(strategy_config.get("provide_history", True))
    history_plies = int(strategy_config.get("history_plies", 8))
    use_system_prompt = bool(strategy_config.get("use_system_prompt", False))

    phase = normalize_phase(game_state.phase)
    prompt_resolution = resolve_system_prompt(
        system_prompt_id=_as_optional_str(strategy_config.get("system_prompt_id")) or DEFAULT_PROMPT_ID,
        variables={
            "color": str(game_state.active_color),
            "phase": phase,
        },
        custom_template=_as_optional_str(strategy_config.get("system_prompt_template")),
    )

    base_lines = [
        f"Phase: {phase}",
        f"Side to move: {game_state.active_color}",
        *board_context_lines(game_state.fen, board_format, game_state.pgn),
    ]

    optional_blocks: dict[str, str] = {}

    few_shot_meta = render_few_shot_block_with_metadata(strategy_config, phase=phase)
    if few_shot_meta.block:
        optional_blocks["few_shot"] = few_shot_meta.block

    rag_cfg = strategy_config.get("rag", {})
    rag_result = query_knowledge(game_state, rag_cfg)
    rag_block = _render_rag_block(rag_result=rag_result, rag_cfg=rag_cfg)
    if rag_block:
        optional_blocks["rag"] = rag_block

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

    user_prompt = "\n".join(lines)
    if dropped:
        user_prompt = "\n".join(
            [user_prompt, f"Context compression: dropped {', '.join(dropped)}."]
        )

    if max_prompt_chars is not None and len(user_prompt) > max_prompt_chars:
        user_prompt = _truncate_prompt(user_prompt, max_prompt_chars)

    selected_system_template = prompt_resolution.rendered_template.strip()
    system_content = selected_system_template if use_system_prompt else None
    if system_content:
        prompt = f"{system_content}\n\n{user_prompt}"
    else:
        prompt = f"{selected_system_template}\n\n{user_prompt}"
        if max_prompt_chars is not None and len(prompt) > max_prompt_chars:
            prompt = _truncate_prompt(prompt, max_prompt_chars)

    retrieval_telemetry = PromptRetrievalTelemetry(
        enabled=bool(isinstance(rag_cfg, dict) and rag_cfg.get("enabled", False)),
        hit_count=len(getattr(rag_result, "chunks", [])),
        latency_ms=int(getattr(rag_result, "latency_ms", 0)),
        sources=list(getattr(rag_result, "sources", []) or []),
        phase=phase,
    )
    few_shot_injected = (
        0 if "few_shot" in dropped else int(few_shot_meta.example_count)
    )
    return PromptBuildResult(
        prompt=prompt,
        dropped_blocks=dropped,
        retrieval=retrieval_telemetry,
        few_shot_examples_injected=few_shot_injected,
        system_content=system_content,
        user_content=user_prompt,
        prompt_id_requested=prompt_resolution.requested_id,
        prompt_id_effective=prompt_resolution.effective_id,
        prompt_label=prompt_resolution.label,
    )


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
    for key in ("few_shot", "rag", "history", "legal_moves", "retry_feedback"):
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
        if key in {"few_shot", "rag", "history", "legal_moves", "retry_feedback"} and key not in normalized:
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


def _render_rag_block(rag_result: Any, rag_cfg: Any) -> str | None:
    chunks = getattr(rag_result, "chunks", None)
    if not isinstance(chunks, list) or not chunks:
        return None
    max_chars_per_chunk = _read_positive_int(rag_cfg, "max_chars_per_chunk")
    if max_chars_per_chunk is None:
        max_chars_per_chunk = DEFAULT_MAX_CHARS_PER_CHUNK

    lines = ["Knowledge snippets (retrieved):"]
    for index, chunk in enumerate(chunks, start=1):
        payload = getattr(chunk, "chunk", None)
        if payload is None:
            continue
        source = getattr(payload, "source", "unknown")
        phase = getattr(payload, "phase", "unknown")
        title = getattr(payload, "title", "Untitled")
        content = str(getattr(payload, "content", "")).strip().replace("\n", " ")
        if len(content) > max_chars_per_chunk:
            content = f"{content[: max_chars_per_chunk - 3].rstrip()}..."
        score = float(getattr(chunk, "score", 0.0))
        lines.append(f"{index}. [{source}/{phase} score={score:.2f}] {title}: {content}")
    if len(lines) <= 1:
        return None
    lines.append("Use snippets only as optional guidance. Return one legal UCI move.")
    return "\n".join(lines)


def _as_optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        parsed = value.strip()
        return parsed or None
    return None
