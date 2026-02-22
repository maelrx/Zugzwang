from __future__ import annotations

from pathlib import Path

from zugzwang.experiments.runner import ExperimentRunner
from zugzwang.providers.base import ProviderResponse
from zugzwang.providers.mock import MockProvider


ROOT = Path(__file__).resolve().parents[2]


def test_runner_stops_when_projected_budget_exceeds_cap(tmp_path: Path, monkeypatch) -> None:
    original_complete = MockProvider.complete

    def expensive_complete(self, messages, model_config):  # type: ignore[no-untyped-def]
        response = original_complete(self, messages, model_config)
        return ProviderResponse(
            text=response.text,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
            cost_usd=1.0,
        )

    monkeypatch.setattr(MockProvider, "complete", expensive_complete)

    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=3",
            "experiment.max_games=3",
            "runtime.max_plies=2",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "budget.max_total_usd=1.5",
            "budget.estimated_avg_cost_per_game_usd=1.0",
        ],
    )
    payload = runner.run()
    assert payload["stopped_due_to_budget"] is True
    assert payload["budget_stop_reason"] == "projected_budget_exceeded"
    assert payload["games_written"] == 0
