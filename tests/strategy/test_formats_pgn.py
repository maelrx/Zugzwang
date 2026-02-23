from __future__ import annotations

import pytest

from zugzwang.core.models import GameState
from zugzwang.strategy.context import build_direct_prompt
from zugzwang.strategy.formats import board_context_lines


def _state(phase: str, pgn: str) -> GameState:
    return GameState(
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        pgn=pgn,
        move_number=1,
        ply_number=0,
        active_color="white",
        legal_moves_uci=["e2e4", "d2d4", "g1f3"],
        legal_moves_san=["e4", "d4", "Nf3"],
        phase=phase,
        is_check=False,
        is_terminal=False,
        termination_reason=None,
        history_uci=[],
    )


def test_board_context_lines_renders_pgn_when_available() -> None:
    lines = board_context_lines(
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        board_format="pgn",
        pgn="1. e4 e5 2. Nf3 Nc6",
    )

    assert lines == ["PGN: 1. e4 e5 2. Nf3 Nc6"]


def test_board_context_lines_falls_back_to_fen_when_pgn_missing() -> None:
    lines = board_context_lines(
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        board_format="pgn",
        pgn="",
    )

    assert lines[0].startswith("PGN:")
    assert lines[1].startswith("FEN:")


@pytest.mark.parametrize(
    ("phase", "pgn"),
    [
        ("opening", "1. e4 e5 2. Nf3 Nc6"),
        ("middlegame", "1. d4 Nf6 2. c4 e6 3. Nc3 Bb4"),
        ("endgame", "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Bxc6 dxc6"),
    ],
)
def test_context_prompt_supports_pgn_format_in_all_phases(phase: str, pgn: str) -> None:
    prompt = build_direct_prompt(
        _state(phase, pgn),
        {
            "board_format": "pgn",
            "provide_legal_moves": False,
            "provide_history": False,
            "validation": {"feedback_level": "rich"},
        },
    )

    assert "PGN:" in prompt
    assert pgn in prompt
