from __future__ import annotations

ALLOWED_PHASES = {"opening", "middlegame", "endgame"}


def normalize_phase(phase: str | None) -> str:
    if not isinstance(phase, str):
        return "middlegame"
    normalized = phase.strip().lower()
    if normalized in ALLOWED_PHASES:
        return normalized
    return "middlegame"
