from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from zugzwang.core.models import GameRecord
from zugzwang.experiments.io import load_game_record


NON_VALID_TERMINATIONS = {"error", "timeout", "provider_failure"}


@dataclass
class ResolvedResumeState:
    run_id: str
    run_dir: Path
    resumed: bool
    existing_records: list[GameRecord]

    @property
    def existing_games(self) -> int:
        return len(self.existing_records)

    @property
    def existing_valid_games(self) -> int:
        return count_valid_games(self.existing_records)

    @property
    def next_game_number(self) -> int:
        if not self.existing_records:
            return 1
        return max(record.game_number for record in self.existing_records) + 1


def is_valid_game_record(record: GameRecord) -> bool:
    return record.termination not in NON_VALID_TERMINATIONS


def count_valid_games(records: list[GameRecord]) -> int:
    return sum(1 for record in records if is_valid_game_record(record))


def load_existing_game_records(run_dir: str | Path) -> list[GameRecord]:
    games_dir = Path(run_dir) / "games"
    if not games_dir.exists():
        return []

    by_game_number: dict[int, tuple[float, GameRecord]] = {}
    for game_path in sorted(games_dir.glob("game_*.json")):
        try:
            record = load_game_record(game_path)
        except (OSError, json.JSONDecodeError, ValueError):
            # Ignore malformed artifacts and continue resume from valid records only.
            continue
        mtime = game_path.stat().st_mtime
        current = by_game_number.get(record.game_number)
        if current is None or mtime >= current[0]:
            by_game_number[record.game_number] = (mtime, record)

    return [record for _, record in sorted(by_game_number.values(), key=lambda item: item[1].game_number)]


def resolve_resume_state(
    output_root: str | Path,
    experiment_name: str,
    config_hash: str,
    generated_run_id: str,
    *,
    resume: bool = False,
    resume_run_id: str | None = None,
) -> ResolvedResumeState:
    output_root_path = Path(output_root)
    if resume_run_id:
        run_dir = output_root_path / resume_run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Requested resume run_id '{resume_run_id}' not found in {output_root_path}")
        run_config_hash = _read_config_hash(run_dir)
        if run_config_hash and run_config_hash != config_hash:
            raise ValueError(
                f"Cannot resume run '{resume_run_id}': config hash mismatch "
                f"(existing={run_config_hash}, current={config_hash})"
            )
        return ResolvedResumeState(
            run_id=run_dir.name,
            run_dir=run_dir,
            resumed=True,
            existing_records=load_existing_game_records(run_dir),
        )

    if resume:
        latest = _find_latest_matching_run(output_root_path, experiment_name, config_hash)
        if latest is not None:
            return ResolvedResumeState(
                run_id=latest.name,
                run_dir=latest,
                resumed=True,
                existing_records=load_existing_game_records(latest),
            )

    run_dir = output_root_path / generated_run_id
    return ResolvedResumeState(
        run_id=generated_run_id,
        run_dir=run_dir,
        resumed=False,
        existing_records=[],
    )


def _find_latest_matching_run(output_root: Path, experiment_name: str, config_hash: str) -> Path | None:
    if not output_root.exists():
        return None

    prefix = f"{experiment_name}-"
    candidates: list[Path] = []
    for run_dir in output_root.iterdir():
        if not run_dir.is_dir():
            continue
        if not run_dir.name.startswith(prefix):
            continue
        if _read_config_hash(run_dir) != config_hash:
            continue
        candidates.append(run_dir)

    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _read_config_hash(run_dir: Path) -> str | None:
    path = run_dir / "config_hash.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip() or None
