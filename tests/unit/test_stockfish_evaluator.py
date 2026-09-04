"""Precision checks for the real Stockfish post-hoc evaluator."""

from __future__ import annotations

from typing import Any

import pytest

from zugzwang_core.ports.evaluator import EvaluationContext


class PositionAwareEngine:
    def __init__(self) -> None:
        self.positions: list[tuple[str, list[str] | None]] = []

    async def start(self) -> None:
        return None

    async def position(self, fen: str, moves: list[str] | None = None) -> None:
        self.positions.append((fen, moves))

    async def go(self, limit: dict[str, int], multipv: int = 1) -> Any:
        from zgw_eval_stockfish.uci import EngineAnalysis, EngineScore

        if len(self.positions) == 1:
            return EngineAnalysis(
                scores=(EngineScore(kind="cp", value=300),),
                bestmove="e2e4",
            )
        return EngineAnalysis(scores=(EngineScore(kind="cp", value=0),), bestmove="a7a6")

    async def quit(self) -> None:
        return None


def test_cp_score_preserves_the_root_side_to_move_perspective() -> None:
    from zgw_eval_stockfish.evaluator import cp_score
    from zgw_eval_stockfish.uci import EngineAnalysis, EngineScore

    analysis = EngineAnalysis(scores=(EngineScore(kind="cp", value=240),))
    assert cp_score(analysis, "white") == 240
    assert cp_score(analysis, "black") == 240


def test_uci_info_keeps_multipv_wdl_and_principal_variation() -> None:
    from zgw_eval_stockfish.uci import _parse_info_pv, _parse_info_score

    line = "info depth 18 multipv 2 score cp 42 wdl 12 80 8 pv g1f3 g8f6"
    score = _parse_info_score(line, 1)
    assert score is not None
    assert score.multipv == 2
    assert score.wdl == (12, 80, 8)
    assert _parse_info_pv(line) == ("g1f3", "g8f6")


@pytest.mark.asyncio
async def test_cpl_compares_the_same_move_before_and_after_without_replaying_history() -> None:
    from zgw_eval_stockfish.evaluator import StockfishEvaluator

    engine = PositionAwareEngine()
    result = await StockfishEvaluator(engine, limit={"nodes": 20_000}).evaluate(
        EvaluationContext(
            run_id="run_test",
            evaluator_config={
                "steps": [
                    {
                        "episode_id": "ep_test",
                        "step_id": "step_test",
                        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                        "moves": ["e2e4"],
                        "action": "e2e4",
                        "side_to_move": "white",
                        "fullmove_number": 1,
                    }
                ]
            },
        )
    )

    values = {observation.metric_id: observation for observation in result.observations}
    assert values["chess.cpl"].value_num == 300
    assert values["chess.engine_best_move"].value_text == "e2e4"
    assert values["chess.engine_score_before"].value_num == 300
    assert values["chess.engine_score_after"].value_num == 0
    assert values["chess.cp_before"].value_num == 300
    assert values["chess.cp_after_chosen"].value_num == 0
    assert values["chess.mate_transition"].value_text == "none"
    assert engine.positions[0][1] is None
    assert engine.positions[1][1] is None
