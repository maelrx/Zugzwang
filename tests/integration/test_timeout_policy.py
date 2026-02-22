from __future__ import annotations

import json
from pathlib import Path

from zugzwang.core.game import play_game as real_play_game
from zugzwang.experiments.runner import ExperimentRunner
from zugzwang.providers.base import ProviderError
from zugzwang.providers.mock import MockProvider


ROOT = Path(__file__).resolve().parents[2]


def test_runner_stops_when_provider_timeout_rate_exceeds_policy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def timeout_complete(self, messages, model_config):  # type: ignore[no-untyped-def]
        raise ProviderError("simulated timeout", category="timeout", retryable=True)

    monkeypatch.setattr(MockProvider, "complete", timeout_complete)

    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=5",
            "experiment.max_games=5",
            "runtime.max_plies=2",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "strategy.validation.provider_retries=0",
            "strategy.validation.move_retries=0",
            "runtime.timeout_policy.enabled=true",
            "runtime.timeout_policy.min_games_before_enforcement=2",
            "runtime.timeout_policy.max_provider_timeout_game_rate=0.5",
            "runtime.timeout_policy.min_observed_completion_rate=0.0",
            "runtime.timeout_policy.action=stop_run",
        ],
    )
    payload = runner.run()

    assert payload["stopped_due_to_reliability"] is True
    assert payload["reliability_stop_reason"] == "provider_timeout_rate_exceeded"
    assert payload["games_written"] == 2
    assert payload["provider_timeout_game_rate"] == 1.0

    run_dir = Path(payload["run_dir"])
    report = json.loads((run_dir / "experiment_report.json").read_text(encoding="utf-8"))
    assert report["stopped_due_to_reliability"] is True
    assert report["reliability_stop_reason"] == "provider_timeout_rate_exceeded"
    assert report["provider_timeout_game_rate"] == 1.0


def test_runner_stops_when_observed_completion_collapses(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def timeout_termination_play_game(*args, **kwargs):  # type: ignore[no-untyped-def]
        record = real_play_game(*args, **kwargs)
        record.termination = "timeout"
        return record

    monkeypatch.setattr("zugzwang.experiments.runner.play_game", timeout_termination_play_game)

    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=5",
            "experiment.max_games=5",
            "players.black.type=random",
            "players.black.name=random_black",
            "runtime.max_plies=2",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "runtime.timeout_policy.enabled=true",
            "runtime.timeout_policy.min_games_before_enforcement=2",
            "runtime.timeout_policy.max_provider_timeout_game_rate=1.0",
            "runtime.timeout_policy.min_observed_completion_rate=0.8",
            "runtime.timeout_policy.action=stop_run",
        ],
    )
    payload = runner.run()

    assert payload["stopped_due_to_reliability"] is True
    assert payload["reliability_stop_reason"] == "completion_rate_below_threshold"
    assert payload["games_written"] == 2
    assert payload["valid_games"] == 0

    run_dir = Path(payload["run_dir"])
    report = json.loads((run_dir / "experiment_report.json").read_text(encoding="utf-8"))
    assert report["stopped_due_to_reliability"] is True
    assert report["reliability_stop_reason"] == "completion_rate_below_threshold"
    assert report["nonvalid_game_rate"] == 1.0
