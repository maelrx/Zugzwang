from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from zugzwang.core.models import ExperimentReport, GameRecord

RUN_METADATA_SCHEMA_VERSION = "1.0"
REDACTED = "***REDACTED***"
SENSITIVE_KEY_MARKERS = (
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "private_key",
)


def ensure_run_dirs(root_output: str | Path, run_id: str) -> Path:
    run_dir = Path(root_output) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "games").mkdir(parents=True, exist_ok=True)
    return run_dir


def write_resolved_config(run_dir: str | Path, config: dict[str, Any], config_hash_value: str) -> None:
    run_dir_path = Path(run_dir)
    (run_dir_path / "resolved_config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=True), encoding="utf-8"
    )
    (run_dir_path / "config_hash.txt").write_text(config_hash_value, encoding="utf-8")


def sanitize_for_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in SENSITIVE_KEY_MARKERS):
                sanitized[key] = REDACTED
                continue
            sanitized[key] = sanitize_for_metadata(child)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_metadata(item) for item in value]
    return value


def write_run_metadata(run_dir: str | Path, metadata: dict[str, Any]) -> Path:
    payload = sanitize_for_metadata(metadata)
    payload["schema_version"] = RUN_METADATA_SCHEMA_VERSION
    path = Path(run_dir) / "_run.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_game_record(run_dir: str | Path, game_record: GameRecord) -> Path:
    path = Path(run_dir) / "games" / f"game_{game_record.game_number:04d}.json"
    path.write_text(json.dumps(game_record.to_dict(), indent=2), encoding="utf-8")
    return path


def write_experiment_report(run_dir: str | Path, report: ExperimentReport) -> Path:
    path = Path(run_dir) / "experiment_report.json"
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path


def write_prompt_transcript(
    *,
    run_dir: str | Path,
    game_number: int,
    ply_number: int,
    retry_index: int,
    payload: dict[str, Any],
) -> Path:
    game_dir = Path(run_dir) / "games" / f"game_{game_number:04d}" / "transcripts"
    game_dir.mkdir(parents=True, exist_ok=True)

    safe_payload = sanitize_for_metadata(payload)
    safe_payload["schema_version"] = RUN_METADATA_SCHEMA_VERSION
    safe_payload["game_number"] = int(game_number)
    safe_payload["ply_number"] = int(ply_number)
    safe_payload["retry_index"] = int(retry_index)

    path = game_dir / f"{ply_number:03d}_{retry_index:02d}.json"
    path.write_text(json.dumps(safe_payload, indent=2), encoding="utf-8")
    return path
