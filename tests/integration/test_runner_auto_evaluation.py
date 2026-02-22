from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]


def test_runner_auto_evaluates_when_enabled(tmp_path: Path, monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_evaluate_run_dir(  # type: ignore[no-untyped-def]
        run_dir,
        player_color="black",
        opponent_elo=None,
        elo_color_correction=0.0,
        output_filename="experiment_report_evaluated.json",
    ):
        run_path = Path(run_dir)
        output_path = run_path / output_filename
        output_path.write_text("{}", encoding="utf-8")

        calls["run_dir"] = str(run_path)
        calls["player_color"] = player_color
        calls["opponent_elo"] = opponent_elo
        calls["elo_color_correction"] = elo_color_correction
        calls["output_filename"] = output_filename

        return {
            "run_dir": str(run_path),
            "output_report": str(output_path),
            "acpl_overall": 12.0,
        }

    monkeypatch.setattr("zugzwang.experiments.runner.evaluate_run_dir", fake_evaluate_run_dir)

    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            "runtime.max_plies=6",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "evaluation.auto.enabled=true",
            "evaluation.auto.player_color=white",
            "evaluation.auto.opponent_elo=1500",
            "evaluation.auto.elo_color_correction=20",
            "evaluation.auto.output_filename=auto_eval_report.json",
        ],
    )
    payload = runner.run()

    assert payload["evaluation"]["status"] == "completed"
    assert calls["player_color"] == "white"
    assert calls["opponent_elo"] == 1500.0
    assert calls["elo_color_correction"] == 20.0
    assert calls["output_filename"] == "auto_eval_report.json"


def test_runner_auto_evaluation_error_is_non_fatal_by_default(tmp_path: Path, monkeypatch) -> None:
    def failing_evaluate(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("stockfish missing")

    monkeypatch.setattr("zugzwang.experiments.runner.evaluate_run_dir", failing_evaluate)

    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            "runtime.max_plies=6",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "evaluation.auto.enabled=true",
        ],
    )
    payload = runner.run()

    assert payload["evaluation"]["status"] == "failed"
    assert "stockfish missing" in payload["evaluation"]["error"]


def test_runner_auto_evaluation_can_fail_hard(tmp_path: Path, monkeypatch) -> None:
    def failing_evaluate(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("evaluation crash")

    monkeypatch.setattr("zugzwang.experiments.runner.evaluate_run_dir", failing_evaluate)

    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            "runtime.max_plies=6",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "evaluation.auto.enabled=true",
            "evaluation.auto.fail_on_error=true",
        ],
    )

    with pytest.raises(RuntimeError, match="evaluation crash"):
        runner.run()
