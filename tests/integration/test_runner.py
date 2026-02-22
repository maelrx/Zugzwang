from __future__ import annotations

import json
from pathlib import Path

from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]


def _run_once(config_name: str, tmp_path: Path, extra_overrides: list[str] | None = None) -> dict:
    config_path = ROOT / "configs" / "baselines" / config_name
    overrides = [
        "experiment.target_valid_games=1",
        "experiment.max_games=1",
        "runtime.max_plies=20",
        f"runtime.output_dir={tmp_path.as_posix()}",
    ]
    if extra_overrides:
        overrides.extend(extra_overrides)
    runner = ExperimentRunner(config_path=config_path, overrides=overrides)
    return runner.run()


def test_random_vs_random_runs_full_pipeline(tmp_path: Path) -> None:
    payload = _run_once(
        "best_known_start.yaml",
        tmp_path,
        extra_overrides=[
            "players.black.type=random",
            "players.black.name=random_black",
        ],
    )
    run_dir = Path(payload["run_dir"])
    assert payload["games_written"] == 1
    assert (run_dir / "games" / "game_0001.json").exists()
    assert (run_dir / "experiment_report.json").exists()


def test_mock_llm_direct_mode(tmp_path: Path) -> None:
    payload = _run_once("best_known_start.yaml", tmp_path)
    run_dir = Path(payload["run_dir"])
    game_data = json.loads((run_dir / "games" / "game_0001.json").read_text(encoding="utf-8"))
    assert game_data["players"]["black"]["type"] == "llm"
    assert game_data["moves"]


def test_mock_llm_agentic_compat_mode(tmp_path: Path) -> None:
    payload = _run_once("benchmark_compat.yaml", tmp_path)
    run_dir = Path(payload["run_dir"])
    game_data = json.loads((run_dir / "games" / "game_0001.json").read_text(encoding="utf-8"))
    assert game_data["players"]["black"]["type"] == "llm"
    assert game_data["moves"]


def test_mock_llm_direct_mode_with_rag_enabled(tmp_path: Path) -> None:
    payload = _run_once(
        "best_known_start.yaml",
        tmp_path,
        extra_overrides=[
            "strategy.rag.enabled=true",
            "strategy.rag.max_chunks=2",
            "strategy.rag.include_sources.eco=true",
            "strategy.rag.include_sources.lichess=false",
            "strategy.rag.include_sources.endgames=false",
        ],
    )
    run_dir = Path(payload["run_dir"])
    game_data = json.loads((run_dir / "games" / "game_0001.json").read_text(encoding="utf-8"))
    assert payload["games_written"] == 1
    assert game_data["players"]["black"]["type"] == "llm"
    assert game_data["moves"]


def test_mock_llm_direct_mode_with_capability_moa_enabled(tmp_path: Path) -> None:
    payload = _run_once(
        "best_known_start.yaml",
        tmp_path,
        extra_overrides=[
            "strategy.multi_agent.enabled=true",
            "strategy.multi_agent.mode=capability_moa",
            "strategy.multi_agent.proposer_count=2",
        ],
    )
    run_dir = Path(payload["run_dir"])
    game_data = json.loads((run_dir / "games" / "game_0001.json").read_text(encoding="utf-8"))
    black_move = next(
        move["move_decision"]
        for move in game_data["moves"]
        if move.get("color") == "black"
    )
    assert payload["games_written"] == 1
    assert black_move["decision_mode"] == "capability_moa"
    assert black_move["provider_calls"] >= 3
    assert isinstance(black_move["agent_trace"], list)
