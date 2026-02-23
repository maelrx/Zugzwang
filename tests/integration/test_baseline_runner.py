from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]
BASELINES = [
    "random_legal.yaml",
    "stockfish_elo_800.yaml",
    "stockfish_elo_1200.yaml",
    "stockfish_elo_1600.yaml",
    "stockfish_elo_2000.yaml",
    "llm_mirror.yaml",
]


@pytest.mark.parametrize("baseline_name", BASELINES)
def test_m2_baselines_run_with_auto_eval(tmp_path: Path, monkeypatch, baseline_name: str) -> None:
    calls: dict[str, object] = {}

    def fake_evaluate_run_dir(  # type: ignore[no-untyped-def]
        run_dir,
        player_color="auto",
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
        return {"run_dir": str(run_path), "output_report": str(output_path)}

    monkeypatch.setattr("zugzwang.experiments.runner.evaluate_run_dir", fake_evaluate_run_dir)

    config_path = ROOT / "configs" / "baselines" / baseline_name
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            "runtime.max_plies=8",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "evaluation.auto.enabled=true",
        ],
    )
    payload = runner.run()

    assert payload["games_written"] == 1
    assert payload["evaluation"]["status"] == "completed"
    assert calls["player_color"] == "auto"
