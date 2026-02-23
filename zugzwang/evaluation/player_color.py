from __future__ import annotations

from typing import Any, Literal


EvalPlayerColor = Literal["white", "black"]

_PLAYER_TYPE_RANK = {
    "llm": 3,
    "engine": 2,
    "random": 1,
}


def infer_evaluation_player_color(
    resolved_config: dict[str, Any] | None,
    requested_color: str | None = "auto",
) -> tuple[EvalPlayerColor, str]:
    normalized = (requested_color or "auto").strip().lower()
    if normalized in {"white", "black"}:
        return normalized, "explicit"
    if normalized != "auto":
        raise ValueError("player_color must be 'auto', 'white' or 'black'")

    if not isinstance(resolved_config, dict):
        return "black", "auto_missing_config_default_black"
    players = resolved_config.get("players")
    if not isinstance(players, dict):
        return "black", "auto_missing_players_default_black"

    white_type = _normalized_player_type(players.get("white"))
    black_type = _normalized_player_type(players.get("black"))
    white_rank = _PLAYER_TYPE_RANK.get(white_type, 0)
    black_rank = _PLAYER_TYPE_RANK.get(black_type, 0)

    if white_rank > black_rank:
        return "white", f"auto_rank_{white_type}_over_{black_type}"
    if black_rank > white_rank:
        return "black", f"auto_rank_{black_type}_over_{white_type}"

    if white_type == black_type and white_type in {"llm", "engine", "random"}:
        return "black", f"auto_tie_{white_type}_default_black"
    return "black", "auto_tie_default_black"


def _normalized_player_type(player_cfg: Any) -> str:
    if not isinstance(player_cfg, dict):
        return "missing"
    raw = str(player_cfg.get("type", "")).strip().lower()
    if raw in {"llm", "engine", "random"}:
        return raw
    return "unknown"
