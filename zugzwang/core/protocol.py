from __future__ import annotations

import re
from typing import Literal

from zugzwang.core.models import GameState
from zugzwang.strategy.formats import board_context_lines


ProtocolMode = Literal["direct", "agentic_compat", "research_strict"]
ActionType = Literal["get_current_board", "get_legal_moves", "make_move", "invalid"]

UCI_PATTERN = re.compile(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", flags=re.IGNORECASE)


def _history_tail(history_uci: list[str], keep_plies: int) -> list[str]:
    if keep_plies <= 0:
        return []
    return history_uci[-keep_plies:]


def build_direct_prompt(game_state: GameState, strategy_config: dict) -> str:
    board_format = strategy_config.get("board_format", "fen")
    include_legal = bool(strategy_config.get("provide_legal_moves", True))
    include_history = bool(strategy_config.get("provide_history", True))
    history_plies = int(strategy_config.get("history_plies", 8))

    lines = [
        "You are a chess assistant playing one move.",
        "Return only one legal move in UCI format.",
        f"Phase: {game_state.phase}",
        f"Side to move: {game_state.active_color}",
        *board_context_lines(game_state.fen, board_format, game_state.pgn),
    ]

    if include_history:
        tail = _history_tail(game_state.history_uci, history_plies)
        lines.append(f"Previous moves (UCI, last {history_plies} plies): {', '.join(tail) if tail else '(none)'}")

    if include_legal:
        lines.append(f"Legal moves (UCI): {', '.join(game_state.legal_moves_uci)}")

    return "\n".join(lines)


def build_agentic_prompt(game_state: GameState) -> str:
    return "\n".join(
        [
            "You are a professional chess player and you play one move.",
            "Before making a move pick one action:",
            "- get_current_board",
            "- get_legal_moves",
            "- make_move <UCI formatted move>",
            "Respond with the action only.",
            f"Current FEN: {game_state.fen}",
        ]
    )


def parse_first_uci(text: str) -> str | None:
    match = UCI_PATTERN.search(text or "")
    if not match:
        return None
    return match.group(0).lower()


def parse_agentic_action(text: str) -> tuple[ActionType, str | None]:
    payload = (text or "").strip().split()
    if not payload:
        return "invalid", None
    action = payload[0].lower()
    if action == "get_current_board":
        return "get_current_board", None
    if action == "get_legal_moves":
        return "get_legal_moves", None
    if action == "make_move":
        if len(payload) < 2:
            return "invalid", None
        move = parse_first_uci(payload[1])
        if not move:
            return "invalid", None
        return "make_move", move
    return "invalid", None
