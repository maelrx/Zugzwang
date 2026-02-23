from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

import yaml

from zugzwang.experiments.runner import ExperimentRunner
from zugzwang.api.services.config_service import ConfigService
from zugzwang.api.services.job_runtime import cancel_job, job_log_tail, refresh_all_jobs, refresh_job, start_job
from zugzwang.api.services.paths import project_root
from zugzwang.api.state.job_store import DEFAULT_JOBS_PATH, get_job, list_jobs
from zugzwang.api.types import CancelResult, JobHandle, RunProgress


RunMode = Literal["dry-run", "run", "play"]


class RunService:
    def __init__(self, jobs_path: str | Path = DEFAULT_JOBS_PATH, cli_module: str = "zugzwang.cli") -> None:
        self.jobs_path = jobs_path
        self.cli_module = cli_module
        self.config_service = ConfigService()

    def start_run(
        self,
        config_path: str,
        model_profile: str | None = None,
        overrides: str | list[str] | None = None,
        mode: RunMode = "run",
    ) -> JobHandle:
        parsed_overrides = self.config_service.parse_overrides(overrides)
        config_path_resolved = self.config_service.resolve_path(config_path)
        config_arg = str(config_path_resolved)
        resolved_profile = self.config_service.resolve_optional_path(model_profile)

        preview_overrides = list(parsed_overrides)
        if mode == "play":
            preview_overrides.extend(
                [
                    "experiment.target_valid_games=1",
                    "experiment.max_games=1",
                ]
            )
        prepared = ExperimentRunner(
            config_path=config_path_resolved,
            model_profile_path=resolved_profile,
            overrides=preview_overrides,
        ).prepare()
        runtime_cfg = prepared.config.get("runtime", {}) if isinstance(prepared.config, dict) else {}
        output_root = runtime_cfg.get("output_dir", "results/runs")
        output_root_path = Path(output_root)
        if not output_root_path.is_absolute():
            output_root_path = project_root() / output_root_path
        run_dir = str(output_root_path / prepared.run_id)

        cmd: list[str] = [
            sys.executable,
            "-m",
            self.cli_module,
        ]

        if mode == "play":
            cmd.append("play")
        else:
            cmd.append("run")
        cmd.extend(["--run-id", prepared.run_id])
        cmd.extend(["--config", config_arg])

        if resolved_profile is not None:
            cmd.extend(["--model-profile", str(resolved_profile)])

        for item in parsed_overrides:
            cmd.extend(["--set", item])

        if mode == "dry-run":
            cmd.append("--dry-run")

        job_type = "play" if mode == "play" else "run"
        meta = {
            "mode": mode,
            "config_path": config_arg,
            "model_profile": str(resolved_profile) if resolved_profile else None,
            "overrides": parsed_overrides,
            "config_hash": prepared.config_hash,
            "scheduled_games": prepared.scheduled_games,
            "estimated_total_cost_usd": prepared.estimated_total_cost_usd,
        }
        return start_job(
            job_type=job_type,
            command=cmd,
            run_id=prepared.run_id,
            run_dir=run_dir,
            meta=meta,
            jobs_path=self.jobs_path,
            working_dir=project_root(),
        )

    def get_run_progress(self, job_id: str) -> RunProgress:
        job = refresh_job(job_id, jobs_path=self.jobs_path) or get_job(job_id, jobs_path=self.jobs_path)
        if not job:
            raise ValueError(f"Unknown job id: {job_id}")

        run_id = _as_string(job.get("run_id"))
        run_dir = _as_string(job.get("run_dir"))
        result_payload = job.get("result_payload")
        if isinstance(result_payload, dict):
            run_id = run_id or _as_string(result_payload.get("run_id"))
            run_dir = run_dir or _as_string(result_payload.get("run_dir"))

        run_path = Path(run_dir) if run_dir else None
        games_written = 0
        games_target: int | None = None
        latest_report: dict[str, Any] | None = None
        stopped_due_to_budget: bool | None = None
        budget_stop_reason: str | None = None

        if run_path and run_path.exists():
            games_dir = run_path / "games"
            if games_dir.exists():
                games_written = len(list(games_dir.glob("game_*.json")))

            report_path = run_path / "experiment_report.json"
            if report_path.exists():
                latest_report = _read_json(report_path)
                if isinstance(latest_report, dict):
                    games_target = _as_int(latest_report.get("num_games_target"))
                    stopped_due_to_budget = bool(latest_report.get("stopped_due_to_budget"))
                    budget_stop_reason = _as_string(latest_report.get("budget_stop_reason"))

            resolved_path = run_path / "resolved_config.yaml"
            if resolved_path.exists() and games_target is None:
                resolved = _read_yaml(resolved_path)
                if isinstance(resolved, dict):
                    experiment = resolved.get("experiment", {})
                    if isinstance(experiment, dict):
                        games_target = _as_int(experiment.get("target_valid_games"))

        log_tail = job_log_tail(job)
        return RunProgress(
            run_id=run_id,
            status=job.get("status", "queued"),
            games_written=games_written,
            games_target=games_target,
            run_dir=run_dir,
            stopped_due_to_budget=stopped_due_to_budget,
            budget_stop_reason=budget_stop_reason,
            latest_report=latest_report,
            log_tail=log_tail,
        )

    def cancel_run(self, job_id: str) -> CancelResult:
        return cancel_job(job_id, jobs_path=self.jobs_path)

    def list_jobs(self, refresh: bool = True) -> list[dict[str, Any]]:
        if refresh:
            return refresh_all_jobs(jobs_path=self.jobs_path)
        return list_jobs(jobs_path=self.jobs_path)

    def get_job(self, job_id: str, refresh: bool = True) -> dict[str, Any] | None:
        if refresh:
            return refresh_job(job_id, jobs_path=self.jobs_path)
        return get_job(job_id, jobs_path=self.jobs_path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _read_yaml(path: Path) -> dict[str, Any] | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _as_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None

