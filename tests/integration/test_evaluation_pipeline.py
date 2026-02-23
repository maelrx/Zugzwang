from __future__ import annotations

import json
from pathlib import Path

import yaml

from zugzwang.evaluation.pipeline import evaluate_run_dir
from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]


def test_evaluate_run_dir_with_stubbed_stockfish(tmp_path: Path, monkeypatch) -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            "runtime.max_plies=6",
            f"runtime.output_dir={tmp_path.as_posix()}",
        ],
    )
    run_payload = runner.run()
    run_dir = Path(run_payload["run_dir"])

    class StubStockfishEvaluator:
        def __init__(self, depth=12, path=None, threads=1, hash_mb=128):
            self.path = path or "stub-stockfish"
            self.depth = depth
            self.threads = threads
            self.hash_mb = hash_mb

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def evaluate_move(self, fen: str, move_uci: str):  # type: ignore[no-untyped-def]
            class Result:
                best_move_uci = move_uci
                centipawn_loss = 12
                eval_before_cp = 20
                eval_after_cp = 8

            return Result()

    monkeypatch.setattr(
        "zugzwang.evaluation.pipeline.StockfishEvaluator",
        StubStockfishEvaluator,
    )

    payload = evaluate_run_dir(run_dir=run_dir, player_color="black")
    report_path = Path(payload["output_report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["evaluated_move_count"] > 0
    assert report["acpl_overall"] == 12.0
    assert report["best_move_agreement"] == 1.0


def test_evaluate_run_dir_auto_infers_white_when_white_is_llm(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run_auto_color"
    games_dir = run_dir / "games"
    games_dir.mkdir(parents=True, exist_ok=True)

    resolved_config = {
        "experiment": {"target_valid_games": 1},
        "budget": {"max_total_usd": 5.0},
        "evaluation": {"stockfish": {"depth": 12, "threads": 1, "hash_mb": 128, "path": None}},
        "players": {
            "white": {"type": "llm", "provider": "mock", "model": "mock-1"},
            "black": {"type": "engine", "level": 10},
        },
    }
    (run_dir / "resolved_config.yaml").write_text(
        yaml.safe_dump(resolved_config, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "config_hash.txt").write_text("hash", encoding="utf-8")
    (run_dir / "experiment_report.json").write_text(
        json.dumps({"num_games_scheduled": 1}),
        encoding="utf-8",
    )

    game_payload = {
        "experiment_id": "exp",
        "game_number": 1,
        "config_hash": "hash",
        "seed": 7,
        "players": resolved_config["players"],
        "moves": [
            {
                "ply_number": 1,
                "color": "white",
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "move_decision": {
                    "move_uci": "e2e4",
                    "move_san": "e4",
                    "raw_response": "e2e4",
                    "parse_ok": True,
                    "is_legal": True,
                    "retry_count": 0,
                    "tokens_input": 10,
                    "tokens_output": 2,
                    "latency_ms": 3,
                    "provider_model": "mock-1",
                },
            },
            {
                "ply_number": 2,
                "color": "black",
                "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                "move_decision": {
                    "move_uci": "e7e5",
                    "move_san": "e5",
                    "raw_response": "e7e5",
                    "parse_ok": True,
                    "is_legal": True,
                    "retry_count": 0,
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "latency_ms": 0,
                    "provider_model": "stockfish",
                },
            },
            {
                "ply_number": 3,
                "color": "white",
                "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                "move_decision": {
                    "move_uci": "g1f3",
                    "move_san": "Nf3",
                    "raw_response": "g1f3",
                    "parse_ok": True,
                    "is_legal": True,
                    "retry_count": 0,
                    "tokens_input": 10,
                    "tokens_output": 2,
                    "latency_ms": 3,
                    "provider_model": "mock-1",
                },
            },
        ],
        "result": "1-0",
        "termination": "checkmate",
        "token_usage": {"input": 20, "output": 4},
        "cost_usd": 0.0,
        "duration_seconds": 1.0,
        "timestamp_utc": "2026-02-22T00:00:00Z",
    }
    (games_dir / "game_0001.json").write_text(json.dumps(game_payload), encoding="utf-8")

    class StubStockfishEvaluator:
        def __init__(self, depth=12, path=None, threads=1, hash_mb=128):
            self.path = path or "stub-stockfish"
            self.depth = depth
            self.threads = threads
            self.hash_mb = hash_mb

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def evaluate_move(self, fen: str, move_uci: str):  # type: ignore[no-untyped-def]
            class Result:
                best_move_uci = move_uci
                centipawn_loss = 10
                eval_before_cp = 0
                eval_after_cp = 0

            return Result()

    monkeypatch.setattr(
        "zugzwang.evaluation.pipeline.StockfishEvaluator",
        StubStockfishEvaluator,
    )

    payload = evaluate_run_dir(run_dir=run_dir, player_color="auto")
    report_path = Path(payload["output_report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["player_color"] == "white"
    assert payload["evaluated_move_count"] == 2
    assert report["evaluation"]["player_color"] == "white"
    assert report["evaluation"]["player_color_requested"] == "auto"


def test_evaluate_run_dir_reports_retrieval_usefulness(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    games_dir = run_dir / "games"
    games_dir.mkdir(parents=True, exist_ok=True)

    resolved_config = {
        "experiment": {"target_valid_games": 1},
        "budget": {"max_total_usd": 5.0},
        "evaluation": {"stockfish": {"depth": 12, "threads": 1, "hash_mb": 128, "path": None}},
    }
    (run_dir / "resolved_config.yaml").write_text(
        yaml.safe_dump(resolved_config, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "config_hash.txt").write_text("hash", encoding="utf-8")
    (run_dir / "experiment_report.json").write_text(
        json.dumps({"num_games_scheduled": 1}),
        encoding="utf-8",
    )

    game_payload = {
        "experiment_id": "exp",
        "game_number": 1,
        "config_hash": "hash",
        "seed": 7,
        "players": {
            "white": {"type": "random"},
            "black": {"type": "llm", "provider": "mock", "model": "mock-1"},
        },
        "moves": [
            {
                "ply_number": 1,
                "color": "white",
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "move_decision": {
                    "move_uci": "e2e4",
                    "move_san": "e4",
                    "raw_response": "e2e4",
                    "parse_ok": True,
                    "is_legal": True,
                    "retry_count": 0,
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "latency_ms": 0,
                    "provider_model": "random",
                },
            },
            {
                "ply_number": 2,
                "color": "black",
                "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                "move_decision": {
                    "move_uci": "e7e5",
                    "move_san": "e5",
                    "raw_response": "e7e5",
                    "parse_ok": True,
                    "is_legal": True,
                    "retry_count": 0,
                    "tokens_input": 10,
                    "tokens_output": 2,
                    "latency_ms": 3,
                    "provider_model": "mock-1",
                    "retrieval_enabled": True,
                    "retrieval_hit_count": 2,
                    "retrieval_latency_ms": 5,
                    "retrieval_sources": ["eco"],
                    "retrieval_phase": "opening",
                },
            },
            {
                "ply_number": 3,
                "color": "white",
                "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                "move_decision": {
                    "move_uci": "g1f3",
                    "move_san": "Nf3",
                    "raw_response": "g1f3",
                    "parse_ok": True,
                    "is_legal": True,
                    "retry_count": 0,
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "latency_ms": 0,
                    "provider_model": "random",
                },
            },
            {
                "ply_number": 4,
                "color": "black",
                "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
                "move_decision": {
                    "move_uci": "b8c6",
                    "move_san": "Nc6",
                    "raw_response": "b8c6",
                    "parse_ok": True,
                    "is_legal": True,
                    "retry_count": 0,
                    "tokens_input": 10,
                    "tokens_output": 2,
                    "latency_ms": 3,
                    "provider_model": "mock-1",
                    "retrieval_enabled": True,
                    "retrieval_hit_count": 0,
                    "retrieval_latency_ms": 4,
                    "retrieval_sources": ["eco"],
                    "retrieval_phase": "opening",
                },
            },
        ],
        "result": "0-1",
        "termination": "checkmate",
        "token_usage": {"input": 20, "output": 4},
        "cost_usd": 0.0,
        "duration_seconds": 1.0,
        "timestamp_utc": "2026-02-22T00:00:00Z",
    }
    (games_dir / "game_0001.json").write_text(json.dumps(game_payload), encoding="utf-8")

    class StubStockfishEvaluator:
        def __init__(self, depth=12, path=None, threads=1, hash_mb=128):
            self.path = path or "stub-stockfish"
            self.depth = depth
            self.threads = threads
            self.hash_mb = hash_mb

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def evaluate_move(self, fen: str, move_uci: str):  # type: ignore[no-untyped-def]
            class Result:
                pass

            output = Result()
            if move_uci == "e7e5":
                output.best_move_uci = "e7e5"
                output.centipawn_loss = 5
            else:
                output.best_move_uci = "g8f6"
                output.centipawn_loss = 40
            output.eval_before_cp = 0
            output.eval_after_cp = 0
            return output

    monkeypatch.setattr(
        "zugzwang.evaluation.pipeline.StockfishEvaluator",
        StubStockfishEvaluator,
    )

    payload = evaluate_run_dir(run_dir=run_dir, player_color="black")
    report_path = Path(payload["output_report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    usefulness = report["retrieval_usefulness"]

    assert usefulness["enabled_move_count"] == 2
    assert usefulness["hit_move_count"] == 1
    assert usefulness["hit_rate"] == 0.5
    assert usefulness["acpl_with_hits"] == 5.0
    assert usefulness["acpl_without_hits"] == 40.0
    assert usefulness["acpl_delta_hit_minus_no_hit"] == -35.0
    assert usefulness["best_move_agreement_with_hits"] == 1.0
    assert usefulness["best_move_agreement_without_hits"] == 0.0
    assert usefulness["hit_count_cp_loss_pearson"] < 0
    assert usefulness["by_phase"]["opening"]["hit_rate"] == 0.5
    assert report["evaluation"]["retrieval_usefulness"]["enabled_move_count"] == 2
