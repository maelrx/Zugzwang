from __future__ import annotations

import json
from pathlib import Path

from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]


def test_runner_persists_prompt_transcripts_when_enabled(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "baselines" / "best_known_start.yaml"
    runner = ExperimentRunner(
        config_path=config_path,
        overrides=[
            "experiment.target_valid_games=1",
            "experiment.max_games=1",
            "runtime.max_plies=8",
            "protocol.mode=research_strict",
            "tracking.persist_prompt_transcripts=true",
            f"runtime.output_dir={tmp_path.as_posix()}",
        ],
    )
    payload = runner.run()
    run_dir = Path(payload["run_dir"])
    transcript_dir = run_dir / "games" / "game_0001" / "transcripts"
    transcript_files = list(transcript_dir.glob("*.json"))

    assert payload["games_written"] == 1
    assert transcript_dir.exists()
    assert transcript_files

    first_payload = json.loads(transcript_files[0].read_text(encoding="utf-8"))
    assert "prompt" in first_payload
    assert "few_shot_examples_injected" in first_payload["prompt"]
