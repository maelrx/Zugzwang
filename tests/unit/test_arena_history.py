"""Arena replay and durable review, fake-only by default (ZGW-0110)."""

from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Any

import chess
import chess.pgn
import pytest

from zugzwang_chess.replay import replay_positions
from zugzwang_cli.arena.game import ArenaGame
from zugzwang_cli.arena.loop import DecisionOutcome
from zugzwang_cli.arena.positions import BoardFacade
from zugzwang_cli.arena.server import ArenaService
from zugzwang_runtime.application.arena_analysis import ArenaAnalysisService


def wait_analysis(service: ArenaAnalysisService, game_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = service.get(game_id)
        if state["status"] in {"complete", "failed"}:
            return state
        time.sleep(0.01)
    raise AssertionError("analysis did not finish")


def fake_review(source: dict[str, Any], completed: int):  # type: ignore[no-untyped-def]
    for row in replay_positions(source["start_fen"], source["moves"])[completed:]:
        yield {**row, "depth": 20, "cp_white": 12, "raw_uci": ["info depth 20 score cp 12"]}


def test_replay_includes_initial_and_all_positions_and_rejects_illegal() -> None:
    rows = replay_positions(chess.STARTING_FEN, ["e2e4", "e7e5", "g1f3"])
    assert len(rows) == 4
    assert rows[0]["fen"] == chess.STARTING_FEN
    assert rows[3]["san"] == "Nf3" and rows[3]["turn"] == "black"
    assert rows[2]["last_uci"] == "e7e5"
    with pytest.raises(ValueError, match="Illegal"):
        replay_positions(chess.STARTING_FEN, ["e2e5"])


def test_auto_review_is_postgame_idempotent_and_survives_restart(tmp_path: Path) -> None:
    profile = {"depth": 20, "evaluator": "fake/1"}
    analysis = ArenaAnalysisService(tmp_path / "analysis", fake_review, profile)
    service = ArenaService(tmp_path / "games", analysis=analysis)
    game = service.create_game({"human_color": "white"})
    assert service.analysis_state(game.game_id)["status"] == "awaiting_finish"
    with pytest.raises(ValueError, match="encerrar"):
        service.analyze(game.game_id)
    assert not list((tmp_path / "analysis").glob("*.json"))
    service.resign(game.game_id)
    result = wait_analysis(analysis, game.game_id)
    assert result["status"] == "complete" and len(result["positions"]) == 1
    assert "raw_uci" not in result["positions"][0]
    service.analyze(game.game_id)
    service.resign(game.game_id)
    assert len(analysis.get(game.game_id)["attempts"]) == 1
    original = (tmp_path / "games" / f"{game.game_id}.json").read_bytes()
    analysis.close()
    restored_analysis = ArenaAnalysisService(tmp_path / "analysis", fake_review, profile)
    restored = ArenaService(tmp_path / "games", analysis=restored_analysis)
    assert restored.analysis_state(game.game_id)["status"] == "complete"
    assert len(restored_analysis.get(game.game_id)["attempts"]) == 1
    assert original == (tmp_path / "games" / f"{game.game_id}.json").read_bytes()
    assert "info depth 20" in next((tmp_path / "analysis").glob("*.jsonl")).read_text()
    restored_analysis.close()


def test_failed_review_preserves_evidence_and_resumes_missing_positions(tmp_path: Path) -> None:
    seen: list[int] = []
    fail = True

    def evaluator(source: dict[str, Any], completed: int):  # type: ignore[no-untyped-def]
        seen.append(completed)
        for row in fake_review(source, completed):
            if fail and row["ply"] == 1:
                raise RuntimeError("engine exited")
            yield row

    analysis = ArenaAnalysisService(tmp_path, evaluator, {"depth": 20})
    source = {"start_fen": chess.STARTING_FEN, "moves": ["e2e4", "e7e5"]}
    analysis.enqueue("arena-test", source, 3)
    first = wait_analysis(analysis, "arena-test")
    assert first["status"] == "failed" and len(first["positions"]) == 1
    raw = next(tmp_path.glob("*.jsonl")).read_bytes()
    analysis.enqueue("arena-test", source, 3)
    assert analysis.get("arena-test")["status"] == "failed"  # no hidden retry
    fail = False
    analysis.enqueue("arena-test", source, 3, retry=True)
    final = wait_analysis(analysis, "arena-test")
    assert final["status"] == "complete"
    assert seen == [0, 1]
    assert [p["ply"] for p in final["positions"]] == [0, 1, 2]
    assert final["attempts"][0]["error"] == "RuntimeError: engine exited"
    assert len(list(tmp_path.glob("*.jsonl"))) == 2
    assert raw in [p.read_bytes() for p in tmp_path.glob("*.jsonl")]
    analysis.close()


def test_interrupted_review_checkpoint_is_resumed(tmp_path: Path) -> None:
    analysis = ArenaAnalysisService(tmp_path, fake_review, {"depth": 20})
    source = {"start_fen": chess.STARTING_FEN, "moves": ["e2e4"]}
    analysis.enqueue("arena-restart", source, 2)
    wait_analysis(analysis, "arena-restart")
    analysis.close()
    path = tmp_path / "arena-restart.json"
    job = json.loads(path.read_text())
    job["positions"] = job["positions"][:1]
    job["status"] = "running"
    path.write_text(json.dumps(job))
    seen: list[int] = []

    def evaluator(source: dict[str, Any], completed: int):  # type: ignore[no-untyped-def]
        seen.append(completed)
        yield from fake_review(source, completed)

    restored = ArenaAnalysisService(tmp_path, evaluator, {"depth": 20})
    restored.enqueue("arena-restart", source, 2)
    assert wait_analysis(restored, "arena-restart")["status"] == "complete"
    assert seen == [1]
    restored.close()


def test_late_model_result_cannot_reopen_resigned_game() -> None:
    game = ArenaGame("arena-test", "2026-09-09T00:00:00", {"human_color": "white"}, BoardFacade())
    game.apply_human_move("e2e4")
    game.resign()
    assert not game.record_model_outcome(
        DecisionOutcome(status="COMMITTED", uci="e7e5"), model_color="black"
    )
    assert game.status == "finished" and len(game.moves) == 1


def test_failure_does_not_allow_human_to_play_model_turn() -> None:
    game = ArenaGame("arena-test", "2026-09-09T00:00:00", {"human_color": "white"}, BoardFacade())
    game.apply_human_move("e2e4")
    game.record_model_outcome(DecisionOutcome(status="PROTOCOL_ERROR"), model_color="black")
    assert game.to_state()["dests"] is None
    with pytest.raises(ValueError):
        game.apply_human_move("e7e5")


def test_pgn_preserves_custom_start_and_promotion() -> None:
    fen = "7k/P7/8/8/8/8/8/7K w - - 0 20"
    game = ArenaGame(
        "arena-test", "2026-09-09T00:00:00", {"human_color": "white"}, BoardFacade(start_fen=fen)
    )
    game.apply_human_move("a7a8q")
    pgn = chess.pgn.read_game(io.StringIO(game.pgn_text()))
    assert pgn is not None and pgn.headers["FEN"] == fen
    assert next(iter(pgn.mainline_moves())).uci() == "a7a8q"
    assert game.to_state()["positions"][-1]["fen"] == game.board.board.fen()


def test_stockfish_profile_depth_and_white_perspective(monkeypatch) -> None:
    from zgw_eval_stockfish import arena_review
    from zgw_eval_stockfish.uci import EngineAnalysis, EngineLine, EngineScore, UciEngineMetadata

    calls: list[Any] = []

    class FakeEngine:
        def __init__(self, executable, *, options):
            calls.append(options)

        async def start(self):
            return UciEngineMetadata(name="Fake Stockfish", author="test")

        async def position(self, fen, moves):
            self.moves = moves
            calls.append(list(moves))

        async def go(self, limit):
            calls.append(limit)
            uci = "e2e4" if not self.moves else "e7e5"
            score = EngineScore(kind="cp", value=30)
            return EngineAnalysis(
                scores=(score,),
                bestmove=uci,
                lines=(EngineLine(score, (uci,)),),
                raw_transcript=(f"info depth 20 score cp 30 pv {uci}", f"bestmove {uci}"),
            )

        async def quit(self):
            calls.append("quit")

    monkeypatch.setattr(arena_review, "UciEngineClient", FakeEngine)
    review = arena_review.StockfishArenaReview("/missing-fake")
    rows = list(review({"start_fen": chess.STARTING_FEN, "moves": ["e2e4"]}, 0))
    assert [row["cp_white"] for row in rows] == [30, -30]
    assert [row["best_san"] for row in rows] == ["e4", "e5"]
    assert [row["pv_san"] for row in rows] == [["e4"], ["e5"]]
    assert calls.count({"depth": 20}) == 2 and calls[-1] == "quit"
    assert ["e2e4"] in calls  # whole move history reaches UCI
