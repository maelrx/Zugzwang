from __future__ import annotations

from zugzwang.core.models import GameState
from zugzwang.strategy.context import build_direct_prompt


def _game_state() -> GameState:
    return GameState(
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        pgn="",
        move_number=1,
        ply_number=0,
        active_color="white",
        legal_moves_uci=["e2e4", "d2d4", "g1f3"],
        legal_moves_san=["e4", "d4", "Nf3"],
        phase="opening",
        is_check=False,
        is_terminal=False,
        termination_reason=None,
        history_uci=["e7e5", "g1f3"],
    )


def test_build_direct_prompt_contains_core_blocks() -> None:
    cfg = {
        "board_format": "fen",
        "provide_legal_moves": True,
        "provide_history": True,
        "history_plies": 8,
        "validation": {"feedback_level": "rich"},
    }

    prompt = build_direct_prompt(_game_state(), cfg)
    assert "FEN:" in prompt
    assert "Legal moves (UCI):" in prompt
    assert "Previous moves (UCI" in prompt


def test_build_direct_prompt_applies_compression() -> None:
    cfg = {
        "board_format": "fen",
        "provide_legal_moves": True,
        "provide_history": True,
        "history_plies": 8,
        "context": {
            "max_prompt_chars": 140,
            "compression_order": ["history", "legal_moves"],
        },
        "validation": {"feedback_level": "rich"},
    }

    prompt = build_direct_prompt(_game_state(), cfg)
    assert len(prompt) <= 152
    assert "Previous moves (UCI" not in prompt


def test_build_direct_prompt_includes_few_shot() -> None:
    cfg = {
        "board_format": "fen",
        "provide_legal_moves": False,
        "provide_history": False,
        "few_shot": {
            "enabled": True,
            "max_examples": 1,
            "by_phase": {
                "opening": [
                    {
                        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                        "move_uci": "e2e4",
                    }
                ]
            },
        },
        "validation": {"feedback_level": "rich"},
    }

    prompt = build_direct_prompt(_game_state(), cfg)
    assert "Few-shot examples" in prompt
    assert "e2e4" in prompt
