from __future__ import annotations

import json
from pathlib import Path

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
