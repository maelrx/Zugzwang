from __future__ import annotations

import re
from dataclasses import dataclass

from zugzwang.strategy.phase import normalize_phase


UCI_PATTERN = re.compile(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", flags=re.IGNORECASE)


@dataclass
class MoveValidationResult:
    move_uci: str | None
    parse_ok: bool
    is_legal: bool
    error_code: str | None


def parse_first_uci(text: str) -> str | None:
    match = UCI_PATTERN.search(text or "")
    if not match:
        return None
    return match.group(0).lower()


def validate_move_response(raw_response: str, legal_moves_uci: list[str]) -> MoveValidationResult:
    move_uci = parse_first_uci(raw_response)
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
