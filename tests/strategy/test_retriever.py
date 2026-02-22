from __future__ import annotations

from zugzwang.core.models import GameState
from zugzwang.knowledge.retriever import query


def _opening_state() -> GameState:
    return GameState(
        fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 2",
        pgn="1. e4 e5 2. Nf3",
        move_number=2,
        ply_number=3,
        active_color="white",
        legal_moves_uci=["f1c4", "d2d4", "b1c3"],
        legal_moves_san=["Bc4", "d4", "Nc3"],
        phase="opening",
        is_check=False,
        is_terminal=False,
        termination_reason=None,
        history_uci=["e2e4", "e7e5", "g1f3"],
    )


def _endgame_state() -> GameState:
    return GameState(
        fen="8/8/8/3k4/3P4/4K3/8/8 w - - 0 1",
        pgn="",
        move_number=1,
        ply_number=0,
        active_color="white",
        legal_moves_uci=["e3d3", "e3e4", "d4d5"],
        legal_moves_san=["Kd3", "Ke4", "d5"],
        phase="endgame",
        is_check=False,
        is_terminal=False,
        termination_reason=None,
        history_uci=[],
    )


def test_query_returns_phase_relevant_opening_chunks() -> None:
    result = query(
        _opening_state(),
        {
            "enabled": True,
            "max_chunks": 2,
            "include_sources": {
                "eco": True,
                "lichess": False,
                "endgames": False,
            },
        },
    )
    assert len(result.chunks) == 2
    assert all(chunk.chunk.source == "eco" for chunk in result.chunks)
    assert all(chunk.chunk.phase == "opening" for chunk in result.chunks)


def test_query_returns_endgame_chunks_when_routed() -> None:
    result = query(
        _endgame_state(),
        {
            "enabled": True,
            "max_chunks": 2,
            "include_sources": {
                "eco": False,
                "lichess": False,
                "endgames": True,
            },
        },
    )
    assert len(result.chunks) == 2
    assert all(chunk.chunk.source == "endgames" for chunk in result.chunks)
    assert all(chunk.chunk.phase == "endgame" for chunk in result.chunks)


def test_query_disabled_returns_empty_result() -> None:
    result = query(_opening_state(), {"enabled": False})
    assert result.chunks == []
    assert result.sources == []
