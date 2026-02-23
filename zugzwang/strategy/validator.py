from __future__ import annotations

import re
from dataclasses import dataclass

import chess

from zugzwang.strategy.phase import normalize_phase


UCI_PATTERN = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b", flags=re.IGNORECASE)
UCI_DASHED_PATTERN = re.compile(
    r"\b([a-h][1-8])-([a-h][1-8])([qrbn]?)\b", flags=re.IGNORECASE
)
UCI_SPACED_PATTERN = re.compile(
    r"\b([a-h][1-8])\s+([a-h][1-8])([qrbn]?)\b", flags=re.IGNORECASE
)


@dataclass
class MoveValidationResult:
    move_uci: str | None
    parse_ok: bool
    is_legal: bool
    error_code: str | None


def parse_first_uci(text: str) -> str | None:
    return normalize_uci_response(text)


def normalize_uci_response(raw_response: str, fen: str | None = None) -> str | None:
    text = str(raw_response or "")

    match = UCI_PATTERN.search(text)
    if match:
        return match.group(1).lower()

    dashed = UCI_DASHED_PATTERN.search(text)
    if dashed:
        return f"{dashed.group(1)}{dashed.group(2)}{dashed.group(3)}".lower()

    spaced = UCI_SPACED_PATTERN.search(text)
    if spaced:
        return f"{spaced.group(1)}{spaced.group(2)}{spaced.group(3)}".lower()

    if not fen:
        return None

    board = _safe_board_from_fen(fen)
    if board is None:
        return None

    # Last-resort SAN parsing when model emits SAN instead of UCI.
    for san_candidate in _extract_san_candidates(text):
        try:
            move = board.parse_san(san_candidate)
        except ValueError:
            continue
        return move.uci()
    return None


def validate_move_response(
    raw_response: str,
    legal_moves_uci: list[str],
    fen: str | None = None,
) -> MoveValidationResult:
    move_uci = normalize_uci_response(raw_response, fen=fen)
    if not move_uci:
        return MoveValidationResult(
            move_uci=None,
            parse_ok=False,
            is_legal=False,
            error_code="parse_failed",
        )

    if move_uci not in legal_moves_uci:
        return MoveValidationResult(
            move_uci=move_uci,
            parse_ok=True,
            is_legal=False,
            error_code="illegal_move",
        )

    return MoveValidationResult(
        move_uci=move_uci,
        parse_ok=True,
        is_legal=True,
        error_code=None,
    )


def _safe_board_from_fen(fen: str) -> chess.Board | None:
    try:
        return chess.Board(fen)
    except ValueError:
        return None


def _extract_san_candidates(raw_response: str) -> list[str]:
    tokens = str(raw_response or "").strip().split()
    candidates: list[str] = []
    for token in tokens:
        candidate = token.strip().rstrip(",.;:!?")
        if candidate:
            candidates.append(candidate)
    return candidates


def build_retry_feedback(
    validation: MoveValidationResult,
    feedback_level: str,
    legal_moves_uci: list[str],
    phase: str,
) -> str:
    level = str(feedback_level or "moderate").lower()
    normalized_phase = normalize_phase(phase)

    if validation.error_code == "parse_failed":
        reason = "No valid UCI move was found in the previous response."
    elif validation.error_code == "illegal_move":
        reason = f"Move '{validation.move_uci}' is illegal in this position."
    else:
        reason = "Previous move output was invalid."

    if level == "minimal":
        return "Return exactly one legal UCI move only."

    if level == "moderate":
        return f"{reason} Return exactly one legal UCI move."

    preview = ", ".join(legal_moves_uci[:20])
    if len(legal_moves_uci) > 20:
        preview += ", ..."
    return (
        f"{reason} Phase={normalized_phase}. "
        "Output must be a single UCI move with no extra text. "
        f"Legal moves include: {preview}"
    )
