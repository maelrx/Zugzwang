from __future__ import annotations

import json
from pathlib import Path

from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]


def test_runner_writes_redacted_run_metadata(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            "runtime.max_plies=6",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "players.black.api_key=super-secret-value",
        ],
    )
    payload = runner.run()
    run_dir = Path(payload["run_dir"])
    metadata_path = run_dir / "_run.json"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["run_metadata"] == str(metadata_path)
    assert metadata["schema_version"] == "1.0"
    assert metadata["run_id"] == payload["run_id"]
    assert metadata["resolved_config"]["players"]["black"]["api_key"] == "***REDACTED***"
    assert metadata["resolved_config"]["strategy"]["system_prompt_id"] == "default"
    assert metadata["resolved_config"]["strategy"]["system_prompt_id_effective"] == "default"
    assert metadata["required_env_vars"] == []


def test_runner_freezes_effective_prompt_id_when_requested_id_is_invalid(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            "runtime.max_plies=6",
            f"runtime.output_dir={tmp_path.as_posix()}",
            "strategy.use_system_prompt=true",
            "strategy.system_prompt_id=unknown_prompt_id",
        ],
    )
    payload = runner.run()
    metadata_path = Path(payload["run_dir"]) / "_run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    strategy = metadata["resolved_config"]["strategy"]
    assert strategy["system_prompt_id_requested"] == "unknown_prompt_id"
    assert strategy["system_prompt_id"] == "default"
    assert strategy["system_prompt_id_effective"] == "default"
