from __future__ import annotations

import chess

from zugzwang.strategy.few_shot import (
    load_few_shot_library,
    render_few_shot_block_with_metadata,
)


def test_load_few_shot_library_from_builtin_source() -> None:
    library = load_few_shot_library({"source": "builtin"})

    assert "opening" in library
    assert "middlegame" in library
    assert "endgame" in library
    assert "default" in library
    assert library["opening"]


def test_render_few_shot_block_uses_builtin_examples() -> None:
    result = render_few_shot_block_with_metadata(
        strategy_config={
            "few_shot": {
                "enabled": True,
                "source": "builtin",
                "max_examples": 2,
            }
        },
        phase="opening",
    )

    assert result.block is not None
    assert result.example_count == 2
    assert "Few-shot examples:" in result.block


def test_load_few_shot_library_uses_inline_config_when_requested() -> None:
    library = load_few_shot_library(
        {
            "source": "config",
            "by_phase": {
                "opening": [
                    {
                        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                        "move_uci": "e2e4",
                    }
                ]
            },
        }
    )

    assert "opening" in library
    assert library["opening"][0]["move_uci"] == "e2e4"


def test_builtin_few_shot_moves_are_legal_for_their_fens() -> None:
    library = load_few_shot_library({"source": "builtin"})

    for phase, entries in library.items():
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            fen = entry.get("fen")
            move_uci = entry.get("move_uci")
            if not isinstance(fen, str) or not isinstance(move_uci, str):
                continue

            board = chess.Board(fen)
            move = chess.Move.from_uci(move_uci)
            assert move in board.legal_moves, f"illegal move in phase={phase}: {fen} -> {move_uci}"
