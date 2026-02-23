from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import yaml

from zugzwang.api.services.paths import runs_root
from zugzwang.api.types import DashboardKpis, DashboardTimelinePoint, GameMeta, GameRecordView, RunMeta, RunSummary
from zugzwang.evaluation.player_color import infer_evaluation_player_color
from zugzwang.providers.model_routing import resolve_provider_and_model


RUN_TS_PATTERN = re.compile(r"-(\d{8}T\d{6}Z)-")
RUN_ID_PATTERN = re.compile(r"^(?P<experiment>.+)-(?P<stamp>\d{8}T\d{6}Z)-(?P<short_hash>[0-9a-fA-F]{8,64})$")


class ArtifactService:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else runs_root()

    def list_runs(self, filters: dict[str, Any] | None = None) -> list[RunMeta]:
        filters = filters or {}
        query = str(filters.get("query", "")).strip().lower()
        evaluated_only = bool(filters.get("evaluated_only", False))
        provider = _as_str(filters.get("provider"))
        model = _as_str(filters.get("model"))
        status = _as_str(filters.get("status"))
        sort_by = _as_str(filters.get("sort_by")) or "created_at_utc"
        sort_dir = (_as_str(filters.get("sort_dir")) or "desc").lower()
        offset = _coerce_int(filters.get("offset"), default=0, minimum=0) or 0
        limit = _coerce_int(filters.get("limit"), default=None, minimum=1)
        date_from = _coerce_date(filters.get("date_from"))
        date_to = _coerce_date(filters.get("date_to"))

        if not self.root.exists():
            return []

        metas: list[RunMeta] = []
        for run_dir in self.root.iterdir():
            if not run_dir.is_dir():
                continue
            if run_dir.name.startswith("_"):
                continue
            meta = self._build_run_meta(run_dir)
            if query:
                haystack = " ".join(
                    value
                    for value in (
                        meta.run_id,
                        meta.inferred_provider,
                        meta.inferred_model,
                        meta.inferred_model_label,
                    )
                    if value
                ).lower()
                if query not in haystack:
                    continue
            if provider and (meta.inferred_provider or "").lower() != provider.lower():
                continue
            if model and (meta.inferred_model or "").lower() != model.lower():
                continue
            if status and not _matches_status(meta, status):
                continue
            if not _matches_date_range(meta.created_at_utc, date_from=date_from, date_to=date_to):
                continue
            if evaluated_only and not meta.evaluated_report_exists:
                continue
            metas.append(meta)

        sort_desc = sort_dir != "asc"
        metas.sort(key=lambda item: _sort_key(item, sort_by, sort_desc), reverse=sort_desc)
        if offset:
            metas = metas[offset:]
        if limit is not None:
            metas = metas[:limit]
        return metas

    def build_dashboard_kpis(self, timeline_limit: int = 40) -> DashboardKpis:
        runs = self.list_runs(filters={"sort_by": "created_at_utc", "sort_dir": "desc"})
        evaluated_runs = [item for item in runs if item.evaluated_report_exists]
        elo_values = [item.elo_estimate for item in evaluated_runs if item.elo_estimate is not None]
        acpl_values = [item.acpl_overall for item in evaluated_runs if item.acpl_overall is not None]
        timeline = [
            DashboardTimelinePoint(
                run_id=item.run_id,
                created_at_utc=item.created_at_utc,
                inferred_model_label=item.inferred_model_label,
                total_cost_usd=item.total_cost_usd,
                elo_estimate=item.elo_estimate,
                acpl_overall=item.acpl_overall,
                evaluated_report_exists=item.evaluated_report_exists,
            )
            for item in runs[: max(0, timeline_limit)]
        ]

        return DashboardKpis(
            total_runs=len(runs),
            runs_with_reports=sum(1 for item in runs if item.report_exists),
            evaluated_runs=len(evaluated_runs),
            best_elo=max(elo_values) if elo_values else None,
            avg_acpl=(sum(acpl_values) / len(acpl_values)) if acpl_values else None,
            total_cost_usd=float(sum(item.total_cost_usd or 0.0 for item in runs)),
            last_run_id=runs[0].run_id if runs else None,
            timeline=timeline,
        )

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

    def save_comparison_artifacts(
        self,
        comparison_id: str,
        payload: dict[str, Any],
        markdown_report: str,
    ) -> dict[str, str]:
        if not comparison_id.strip():
            raise ValueError("comparison_id must not be empty")
        comparison_dir = self._comparisons_root() / comparison_id.strip()
        comparison_dir.mkdir(parents=True, exist_ok=True)

        json_path = comparison_dir / "comparison.json"
        markdown_path = comparison_dir / "report.md"
        artifact_paths = {
            "comparison_dir": str(comparison_dir),
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
        }
        payload_with_paths = dict(payload)
        payload_with_paths["artifacts"] = artifact_paths
        json_path.write_text(json.dumps(payload_with_paths, indent=2), encoding="utf-8")
        markdown_path.write_text(markdown_report, encoding="utf-8")
        return artifact_paths

    def load_comparison_payload(self, comparison_id: str) -> dict[str, Any]:
        path = self._comparison_file(comparison_id, "comparison.json")
        payload = _load_json(path)
        if payload is None:
            raise FileNotFoundError(f"Comparison payload not found: {path}")
        return payload

    def load_comparison_markdown(self, comparison_id: str) -> str:
        path = self._comparison_file(comparison_id, "report.md")
        if not path.exists():
            raise FileNotFoundError(f"Comparison report markdown not found: {path}")
        return path.read_text(encoding="utf-8")

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
            if run_dir.name.startswith("_"):
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

    def _comparisons_root(self) -> Path:
        path = self.root / "_comparisons"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _comparison_file(self, comparison_id: str, name: str) -> Path:
        normalized = comparison_id.strip()
        if not normalized:
            raise FileNotFoundError("comparison_id must not be empty")
        return self._comparisons_root() / normalized / name

    def _build_run_meta(self, run_dir: Path) -> RunMeta:
        run_id = run_dir.name
        created_at = _extract_timestamp(run_id) or _extract_timestamp_from_mtime(run_dir)

        config_hash = None
        config_hash_path = run_dir / "config_hash.txt"
        if config_hash_path.exists():
            config_hash = config_hash_path.read_text(encoding="utf-8").strip() or None

        resolved_config = _load_yaml(run_dir / "resolved_config.yaml")
        report = _load_json(run_dir / "experiment_report.json")
        evaluated_report = _load_json(run_dir / "experiment_report_evaluated.json")

        report_exists = report is not None
        evaluated_exists = evaluated_report is not None
        inferred_player_color = _infer_eval_player_color(resolved_config)
        inferred_provider, inferred_model = _infer_provider_model_for_color(
            resolved_config,
            inferred_player_color,
        )
        if inferred_provider is None and inferred_model is None:
            _, inferred_provider, inferred_model = _infer_llm_player(resolved_config)
        inferred_model_label = _compose_model_label(inferred_provider, inferred_model)
        inferred_opponent_elo = _infer_opponent_elo(resolved_config, inferred_player_color)
        inferred_config_template = _infer_config_template(run_id, resolved_config)
        inferred_eval_status = _infer_eval_status(report_exists=report_exists, evaluated_exists=evaluated_exists)

        num_games_target = _first_int(
            _dict_get(evaluated_report, "num_games_target"),
            _dict_get(report, "num_games_target"),
        )
        num_games_valid = _first_int(
            _dict_get(evaluated_report, "num_games_valid"),
            _dict_get(report, "num_games_valid"),
        )
        completion_rate = _first_float(
            _dict_get(evaluated_report, "completion_rate"),
            _dict_get(report, "completion_rate"),
        )
        total_cost_usd = _first_float(
            _dict_get(evaluated_report, "total_cost_usd"),
            _dict_get(report, "total_cost_usd"),
        )
        elo_estimate = _first_float(
            _dict_get(evaluated_report, "elo_estimate"),
            _dict_get(report, "elo_estimate"),
        )
        acpl_overall = _first_float(
            _dict_get(evaluated_report, "acpl_overall"),
            _dict_get(report, "acpl_overall"),
        )
        blunder_rate = _first_float(
            _dict_get(evaluated_report, "blunder_rate"),
            _dict_get(report, "blunder_rate"),
        )

        return RunMeta(
            run_id=run_id,
            run_dir=str(run_dir),
            created_at_utc=created_at,
            config_hash=config_hash,
            report_exists=report_exists,
            evaluated_report_exists=evaluated_exists,
            inferred_player_color=inferred_player_color,
            inferred_opponent_elo=inferred_opponent_elo,
            inferred_provider=inferred_provider,
            inferred_model=inferred_model,
            inferred_model_label=inferred_model_label,
            inferred_config_template=inferred_config_template,
            inferred_eval_status=inferred_eval_status,
            num_games_target=num_games_target,
            num_games_valid=num_games_valid,
            completion_rate=completion_rate,
            total_cost_usd=total_cost_usd,
            elo_estimate=elo_estimate,
            acpl_overall=acpl_overall,
            blunder_rate=blunder_rate,
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


def _extract_timestamp_from_mtime(path: Path) -> str | None:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat().replace("+00:00", "Z")


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


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _coerce_int(value: Any, default: int | None = None, minimum: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        parsed = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            parsed = int(float(stripped))
        except ValueError:
            return default
    else:
        return default

    if minimum is not None and parsed < minimum:
        return minimum
    return parsed


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return date.fromisoformat(stripped)
        except ValueError:
            return None
    return None


def _dict_get(payload: dict[str, Any] | None, key: str) -> Any:
    if payload is None:
        return None
    return payload.get(key)


def _first_int(*values: Any) -> int | None:
    for value in values:
        parsed = _coerce_int(value, default=None)
        if parsed is not None:
            return parsed
    return None


def _first_float(*values: Any) -> float | None:
    for value in values:
        parsed = _coerce_float(value)
        if parsed is not None:
            return parsed
    return None


def _infer_llm_player(resolved_config: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    if not isinstance(resolved_config, dict):
        return None, None, None
    players = resolved_config.get("players")
    if not isinstance(players, dict):
        return None, None, None

    for color in ("black", "white"):
        player = players.get(color)
        if not isinstance(player, dict):
            continue
        if str(player.get("type", "")).strip().lower() != "llm":
            continue
        return (
            color,
            _as_str(player.get("provider")),
            _as_str(player.get("model")),
        )
    return None, None, None


def _infer_eval_player_color(resolved_config: dict[str, Any] | None) -> str | None:
    if not isinstance(resolved_config, dict):
        return None

    requested = "auto"
    evaluation_cfg = resolved_config.get("evaluation")
    if isinstance(evaluation_cfg, dict):
        auto_cfg = evaluation_cfg.get("auto")
        if isinstance(auto_cfg, dict):
            raw = auto_cfg.get("player_color")
            if isinstance(raw, str) and raw.strip():
                requested = raw

    try:
        color, _ = infer_evaluation_player_color(
            resolved_config=resolved_config,
            requested_color=requested,
        )
    except ValueError:
        return None
    return color


def _infer_provider_model_for_color(
    resolved_config: dict[str, Any] | None,
    color: str | None,
) -> tuple[str | None, str | None]:
    if not isinstance(resolved_config, dict):
        return None, None
    if color not in {"white", "black"}:
        return None, None
    players = resolved_config.get("players")
    if not isinstance(players, dict):
        return None, None
    player = players.get(color)
    if not isinstance(player, dict):
        return None, None
    if str(player.get("type", "")).strip().lower() != "llm":
        return None, None
    resolved_provider, resolved_model = resolve_provider_and_model(
        _as_str(player.get("provider")) or "",
        _as_str(player.get("model")),
    )
    return resolved_provider or None, resolved_model


def _compose_model_label(provider: str | None, model: str | None) -> str | None:
    if provider and model:
        return f"{provider} / {model}"
    return provider or model


def _infer_opponent_elo(resolved_config: dict[str, Any] | None, inferred_player_color: str | None) -> int | None:
    if not isinstance(resolved_config, dict):
        return None
    if inferred_player_color not in {"white", "black"}:
        return None

    players = resolved_config.get("players")
    if not isinstance(players, dict):
        return None

    opponent_color = "white" if inferred_player_color == "black" else "black"
    opponent = players.get(opponent_color)
    if not isinstance(opponent, dict):
        return None

    explicit_elo = _coerce_int(opponent.get("elo"), default=None)
    if explicit_elo is not None:
        return explicit_elo

    stockfish_level = _coerce_int(opponent.get("level"), default=None)
    if stockfish_level is None:
        return None
    return _map_stockfish_level_to_elo(stockfish_level)


def _map_stockfish_level_to_elo(level: int) -> int:
    if level <= 2:
        return 600
    if level <= 5:
        return 800
    if level <= 8:
        return 1000
    if level <= 11:
        return 1200
    if level <= 14:
        return 1600
    if level <= 17:
        return 2000
    return 2500


def _infer_config_template(run_id: str, resolved_config: dict[str, Any] | None) -> str | None:
    if isinstance(resolved_config, dict):
        experiment = resolved_config.get("experiment")
        if isinstance(experiment, dict):
            experiment_name = _as_str(experiment.get("name"))
            if experiment_name:
                return experiment_name

    parsed = _parse_run_id(run_id)
    if parsed is not None:
        return parsed[0]
    return None


def _infer_eval_status(report_exists: bool, evaluated_exists: bool) -> str:
    if evaluated_exists:
        return "evaluated"
    if report_exists:
        return "needs_eval"
    return "pending_report"


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _matches_date_range(created_at_utc: str | None, date_from: date | None, date_to: date | None) -> bool:
    if date_from is None and date_to is None:
        return True
    created = _parse_iso_utc(created_at_utc)
    if created is None:
        return False

    if date_from is not None:
        lower = datetime.combine(date_from, time.min, tzinfo=UTC)
        if created < lower:
            return False
    if date_to is not None:
        upper = datetime.combine(date_to, time.max, tzinfo=UTC)
        if created > upper:
            return False
    return True


def _matches_status(meta: RunMeta, status: str) -> bool:
    normalized = status.strip().lower()
    if normalized in {"all", ""}:
        return True
    if normalized in {"evaluated", "completed_evaluated"}:
        return meta.evaluated_report_exists
    if normalized in {"needs_eval", "pending_evaluation"}:
        return meta.report_exists and not meta.evaluated_report_exists
    if normalized in {"pending_report", "running", "queued"}:
        return not meta.report_exists
    return meta.inferred_eval_status == normalized


def _sort_key(meta: RunMeta, sort_by: str, descending: bool) -> Any:
    normalized = sort_by.strip().lower()
    if normalized in {"run_id", "id"}:
        return meta.run_id.lower()
    if normalized in {"elo", "elo_estimate"}:
        return _numeric_sort_value(meta.elo_estimate, descending)
    if normalized in {"acpl", "acpl_overall"}:
        return _numeric_sort_value(meta.acpl_overall, descending)
    if normalized in {"cost", "total_cost_usd"}:
        return _numeric_sort_value(meta.total_cost_usd, descending)

    created = _parse_iso_utc(meta.created_at_utc)
    if created is None:
        return _numeric_sort_value(None, descending)
    return created.timestamp()


def _numeric_sort_value(value: float | None, descending: bool) -> float:
    if value is None:
        return float("-inf") if descending else float("inf")
    return float(value)

