from __future__ import annotations

from zugzwang.core.models import GameState
from zugzwang.strategy.context import build_direct_prompt, build_direct_prompt_with_metadata


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

    payload = build_direct_prompt_with_metadata(_game_state(), cfg)
    assert "Few-shot examples" in payload.prompt
    assert "e2e4" in payload.prompt
    assert payload.few_shot_examples_injected == 1


def test_build_direct_prompt_tracks_few_shot_count_after_compression() -> None:
    cfg = {
        "board_format": "fen",
        "provide_legal_moves": False,
        "provide_history": False,
        "few_shot": {
            "enabled": True,
            "source": "config",
            "max_examples": 2,
            "by_phase": {
                "opening": [
                    {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "move_uci": "e2e4"},
                    {"fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1", "move_uci": "e7e5"},
                ]
            },
        },
        "context": {
            "max_prompt_chars": 120,
            "compression_order": ["few_shot"],
        },
        "validation": {"feedback_level": "rich"},
    }

    payload = build_direct_prompt_with_metadata(_game_state(), cfg)

    assert "Few-shot examples" not in payload.prompt
    assert payload.few_shot_examples_injected == 0


def test_build_direct_prompt_includes_rag_block_when_enabled() -> None:
    cfg = {
        "board_format": "fen",
        "provide_legal_moves": False,
        "provide_history": False,
        "rag": {
            "enabled": True,
            "max_chunks": 2,
            "include_sources": {
                "eco": True,
                "lichess": False,
                "endgames": False,
            },
        },
        "validation": {"feedback_level": "rich"},
    }

    prompt = build_direct_prompt(_game_state(), cfg)
    assert "Knowledge snippets (retrieved):" in prompt
    assert "[eco/opening" in prompt


def test_build_direct_prompt_can_compress_rag_block() -> None:
    cfg = {
        "board_format": "fen",
        "provide_legal_moves": False,
        "provide_history": False,
        "rag": {
            "enabled": True,
            "max_chunks": 2,
            "include_sources": {
                "eco": True,
                "lichess": True,
                "endgames": True,
            },
        },
        "context": {
            "max_prompt_chars": 280,
            "compression_order": ["rag"],
        },
        "validation": {"feedback_level": "rich"},
    }

    prompt = build_direct_prompt(_game_state(), cfg)
    assert "Knowledge snippets (retrieved):" not in prompt
    assert "Context compression: dropped rag." in prompt


def test_build_direct_prompt_uses_system_prompt_id_and_interpolates_vars() -> None:
    cfg = {
        "use_system_prompt": True,
        "system_prompt_id": "structured_analysis",
        "board_format": "fen",
        "provide_legal_moves": True,
        "provide_history": False,
        "validation": {"feedback_level": "rich"},
    }

    payload = build_direct_prompt_with_metadata(_game_state(), cfg)

    assert payload.prompt_id_requested == "structured_analysis"
    assert payload.prompt_id_effective == "structured_analysis"
    assert payload.system_content is not None
    assert "white" in payload.system_content
    assert "opening" in payload.system_content


def test_build_direct_prompt_falls_back_to_default_for_invalid_prompt_id() -> None:
    cfg = {
        "use_system_prompt": True,
        "system_prompt_id": "does_not_exist",
        "board_format": "fen",
        "provide_legal_moves": True,
        "provide_history": False,
        "validation": {"feedback_level": "rich"},
    }

    payload = build_direct_prompt_with_metadata(_game_state(), cfg)

    assert payload.prompt_id_requested == "does_not_exist"
    assert payload.prompt_id_effective == "default"
    assert payload.system_content is not None
    assert "chess assistant" in payload.system_content
