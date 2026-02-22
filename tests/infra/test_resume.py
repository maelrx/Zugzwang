from __future__ import annotations

import json
import os
import time
from pathlib import Path

from zugzwang.experiments.resume import count_valid_games, load_existing_game_records


def _game_payload(game_number: int, termination: str) -> dict[str, object]:
    return {
        "experiment_id": "exp",
        "game_number": game_number,
        "config_hash": "hash",
        "seed": 1,
        "players": {
            "white": {"type": "random"},
            "black": {"type": "random"},
        },
        "moves": [],
        "result": "*",
        "termination": termination,
        "token_usage": {"input": 0, "output": 0},
        "cost_usd": 0.0,
        "duration_seconds": 0.01,
        "timestamp_utc": "2026-02-22T00:00:00Z",
    }


def test_load_existing_game_records_deduplicates_by_game_number_using_latest_file(tmp_path: Path) -> None:
    games_dir = tmp_path / "games"
    games_dir.mkdir(parents=True, exist_ok=True)

    first_path = games_dir / "game_0001_a.json"
    second_path = games_dir / "game_0001_b.json"
    first_path.write_text(json.dumps(_game_payload(1, "timeout")), encoding="utf-8")
    second_path.write_text(json.dumps(_game_payload(1, "checkmate")), encoding="utf-8")

    base_time = time.time()
    os.utime(first_path, (base_time, base_time))
    os.utime(second_path, (base_time + 5, base_time + 5))

    records = load_existing_game_records(tmp_path)
    assert len(records) == 1
    assert records[0].game_number == 1
    assert records[0].termination == "checkmate"
    assert count_valid_games(records) == 1
