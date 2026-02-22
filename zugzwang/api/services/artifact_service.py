from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from zugzwang.api.services.paths import runs_root
from zugzwang.api.types import GameMeta, GameRecordView, RunMeta, RunSummary


RUN_TS_PATTERN = re.compile(r"-(\d{8}T\d{6}Z)-")
RUN_ID_PATTERN = re.compile(r"^(?P<experiment>.+)-(?P<stamp>\d{8}T\d{6}Z)-(?P<short_hash>[0-9a-fA-F]{8,64})$")


class ArtifactService:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else runs_root()

    def list_runs(self, filters: dict[str, Any] | None = None) -> list[RunMeta]:
        filters = filters or {}
        query = str(filters.get("query", "")).strip().lower()
        evaluated_only = bool(filters.get("evaluated_only", False))

        if not self.root.exists():
            return []

        metas: list[RunMeta] = []
        for run_dir in self.root.iterdir():
            if not run_dir.is_dir():
                continue
            meta = self._build_run_meta(run_dir)
            if query and query not in meta.run_id.lower():
                continue
            if evaluated_only and not meta.evaluated_report_exists:
                continue
            metas.append(meta)

        metas.sort(key=lambda item: item.created_at_utc or "", reverse=True)
        return metas

    def load_run_summary(self, run_dir: str | Path) -> RunSummary:
        path = self._resolve_run_dir(run_dir)
        run_meta = self._build_run_meta(path)

        resolved_config = _load_yaml(path / "resolved_config.yaml")
        report = _load_json(path / "experiment_report.json")
        evaluated_report = _load_json(path / "experiment_report_evaluated.json")
        game_count = len(list((path / "games").glob("game_*.json"))) if (path / "games").exists() else 0

        return RunSummary(
            run_meta=run_meta,
            resolved_config=resolved_config,
            report=report,
            evaluated_report=evaluated_report,
            game_count=game_count,
        )

    def list_games(self, run_dir: str | Path) -> list[GameMeta]:
        path = self._resolve_run_dir(run_dir) / "games"
        if not path.exists():
            return []

        games: list[GameMeta] = []
        for file_path in sorted(path.glob("game_*.json")):
            stem = file_path.stem
            try:
                game_number = int(stem.split("_")[1])
            except (IndexError, ValueError):
                continue
            games.append(GameMeta(game_number=game_number, path=str(file_path)))
        return games

    def load_game(self, run_dir: str | Path, game_number: int) -> GameRecordView:
        run_path = self._resolve_run_dir(run_dir)
        game_path = run_path / "games" / f"game_{game_number:04d}.json"
        payload = _load_json(game_path)
        if not isinstance(payload, dict):
            raise FileNotFoundError(f"Game file not found or invalid: {game_path}")

        result = str(payload.get("result", "*"))
        termination = str(payload.get("termination", "unknown"))
        duration_seconds = float(payload.get("duration_seconds", 0.0))
        total_cost_usd = float(payload.get("cost_usd", 0.0))
        token_usage = payload.get("token_usage", {})
        if not isinstance(token_usage, dict):
            token_usage = {}

        total_tokens = {
            "input": int(token_usage.get("input", 0)),
            "output": int(token_usage.get("output", 0)),
        }
        moves = payload.get("moves", [])
        if not isinstance(moves, list):
            moves = []

        return GameRecordView(
            game_number=int(payload.get("game_number", game_number)),
            result=result,
            termination=termination,
            duration_seconds=duration_seconds,
            total_cost_usd=total_cost_usd,
            total_tokens=total_tokens,
            moves=moves,
        )

    def load_artifact_text(self, run_dir: str | Path, artifact_name: str) -> str:
        path = self._resolve_run_dir(run_dir) / artifact_name
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def _resolve_run_dir(self, run_dir: str | Path) -> Path:
        path = Path(run_dir)
        if path.is_absolute() and path.exists():
            return path

        candidate = self.root / path
        if candidate.exists():
            return candidate
        alias = self._resolve_run_alias(path.name)
        if alias is not None:
            return alias
        if path.exists():
            return path
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    def _resolve_run_alias(self, run_id: str) -> Path | None:
        parsed_requested = _parse_run_id(run_id)
        if parsed_requested is None or not self.root.exists():
            return None

        req_experiment, req_stamp, req_short_hash = parsed_requested
        req_dt = _parse_run_stamp(req_stamp)

        candidates: list[tuple[float, float, Path]] = []
        for run_dir in self.root.iterdir():
            if not run_dir.is_dir():
                continue
            parsed = _parse_run_id(run_dir.name)
            if parsed is None:
                continue
            experiment, stamp, short_hash = parsed
            if experiment != req_experiment or short_hash.lower() != req_short_hash.lower():
                continue

            candidate_dt = _parse_run_stamp(stamp)
            if req_dt and candidate_dt:
                delta = abs((candidate_dt - req_dt).total_seconds())
            else:
                delta = float("inf")
            # Tie-break on most recent mtime so we prefer the freshest matching run.
            candidates.append((delta, -run_dir.stat().st_mtime, run_dir))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2]

    def _build_run_meta(self, run_dir: Path) -> RunMeta:
        run_id = run_dir.name
        created_at = _extract_timestamp(run_id)

        config_hash = None
        config_hash_path = run_dir / "config_hash.txt"
        if config_hash_path.exists():
            config_hash = config_hash_path.read_text(encoding="utf-8").strip() or None

        report_exists = (run_dir / "experiment_report.json").exists()
        evaluated_exists = (run_dir / "experiment_report_evaluated.json").exists()

        return RunMeta(
            run_id=run_id,
            run_dir=str(run_dir),
            created_at_utc=created_at,
            config_hash=config_hash,
            report_exists=report_exists,
            evaluated_report_exists=evaluated_exists,
        )


def _extract_timestamp(run_id: str) -> str | None:
    match = RUN_TS_PATTERN.search(run_id)
    if not match:
        return None
    stamp = match.group(1)
    try:
        parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None
    return parsed.isoformat().replace("+00:00", "Z")


def _parse_run_id(run_id: str) -> tuple[str, str, str] | None:
    match = RUN_ID_PATTERN.match(run_id)
    if not match:
        return None
    return (
        match.group("experiment"),
        match.group("stamp"),
        match.group("short_hash"),
    )


def _parse_run_stamp(stamp: str) -> datetime | None:
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _load_yaml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    return raw

