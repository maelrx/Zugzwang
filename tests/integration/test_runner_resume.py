from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.core.game import play_game as real_play_game
from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]


def test_runner_resumes_interrupted_run_without_duplicate_games(tmp_path: Path, monkeypatch) -> None:
    call_count = {"value": 0}

    def flaky_play_game(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("simulated interruption")
        return real_play_game(*args, **kwargs)

    monkeypatch.setattr("zugzwang.experiments.runner.play_game", flaky_play_game)

    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    overrides = [
        "experiment.target_valid_games=2",
        "experiment.max_games=2",
        "runtime.max_plies=6",
        f"runtime.output_dir={tmp_path.as_posix()}",
    ]
    first_runner = ExperimentRunner(config_path=config_path, overrides=overrides)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        first_runner.run()

    run_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    interrupted_run_dir = run_dirs[0]
    assert (interrupted_run_dir / "games" / "game_0001.json").exists()
    assert not (interrupted_run_dir / "games" / "game_0002.json").exists()

    monkeypatch.setattr("zugzwang.experiments.runner.play_game", real_play_game)

    resumed_runner = ExperimentRunner(
        config_path=config_path,
        overrides=overrides,
        resume=True,
    )
    payload = resumed_runner.run()

    assert payload["resumed"] is True
    assert payload["existing_games_loaded"] == 1
    assert payload["run_id"] == interrupted_run_dir.name
    assert payload["games_written"] == 2
    assert payload["valid_games"] == 2
    assert (interrupted_run_dir / "games" / "game_0001.json").exists()
    assert (interrupted_run_dir / "games" / "game_0002.json").exists()
    assert len(list((interrupted_run_dir / "games").glob("game_*.json"))) == 2


def test_runner_resume_with_missing_run_id_fails_fast(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[f"runtime.output_dir={tmp_path.as_posix()}"],
        resume_run_id="missing-run-id",
    )
    with pytest.raises(FileNotFoundError, match="missing-run-id"):
        runner.run()
