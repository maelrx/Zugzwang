from __future__ import annotations

from pathlib import Path

from zugzwang.core.models import GameRecord
from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]


def test_runner_closes_players_after_game(tmp_path: Path, monkeypatch) -> None:
    closed: list[str] = []
    counter = {"value": 0}

    class _ClosablePlayer:
        def __init__(self, label: str) -> None:
            self.label = label

        def close(self) -> None:
            closed.append(self.label)

    def fake_build_player(*args, **kwargs):  # type: ignore[no-untyped-def]
        idx = counter["value"]
        counter["value"] += 1
        return _ClosablePlayer(label=f"player-{idx}")

    def fake_play_game(*args, **kwargs):  # type: ignore[no-untyped-def]
        return GameRecord(
            experiment_id="exp-1",
            game_number=1,
            config_hash="cfg-1",
            seed=1,
            players={},
            moves=[],
            result="1/2-1/2",
            termination="draw_rule",
            token_usage={"input": 0, "output": 0},
            cost_usd=0.0,
            duration_seconds=0.01,
            timestamp_utc="2026-01-01T00:00:00Z",
        )

    monkeypatch.setattr("zugzwang.experiments.runner.build_player", fake_build_player)
    monkeypatch.setattr("zugzwang.experiments.runner.play_game", fake_play_game)

    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            f"runtime.output_dir={tmp_path.as_posix()}",
        ],
    )
    payload = runner.run()

    assert payload["games_written"] == 1
    assert sorted(closed) == ["player-0", "player-1"]
