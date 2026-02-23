from __future__ import annotations

from pathlib import Path
from typing import Any

from zugzwang.api.services.job_runtime import job_log_tail, refresh_all_jobs, refresh_job, start_job
from zugzwang.api.services.paths import project_root
from zugzwang.api.services.process_utils import python_executable
from zugzwang.api.state.job_store import DEFAULT_JOBS_PATH, get_job, list_jobs
from zugzwang.api.types import EvalResult, JobHandle


class EvaluationService:
    def __init__(self, jobs_path: str | Path = DEFAULT_JOBS_PATH, cli_module: str = "zugzwang.cli") -> None:
        self.jobs_path = jobs_path
        self.cli_module = cli_module

    def start_evaluation(
        self,
        run_dir: str,
        player_color: str = "auto",
        opponent_elo: float | None = None,
        output_filename: str = "experiment_report_evaluated.json",
    ) -> JobHandle:
        command: list[str] = [
            python_executable(),
            "-u",
            "-m",
            self.cli_module,
            "evaluate",
            "--run-dir",
            str(Path(run_dir)),
            "--player-color",
            player_color,
            "--output-filename",
            output_filename,
        ]
        if opponent_elo is not None:
            command.extend(["--opponent-elo", str(opponent_elo)])

        return start_job(
            job_type="evaluate",
            command=command,
            run_dir=str(Path(run_dir)),
            meta={
                "player_color": player_color,
                "opponent_elo": opponent_elo,
                "output_filename": output_filename,
            },
            jobs_path=self.jobs_path,
            working_dir=project_root(),
        )

    def get_evaluation_result(self, job_id: str) -> EvalResult:
        job = refresh_job(job_id, jobs_path=self.jobs_path) or get_job(job_id, jobs_path=self.jobs_path)
        if not job:
            raise ValueError(f"Unknown job id: {job_id}")

        output_report: str | None = None
        payload: dict[str, Any] | None = None

        result_payload = job.get("result_payload")
        if isinstance(result_payload, dict):
            payload = result_payload
            out = result_payload.get("output_report")
            if isinstance(out, str):
                output_report = out

        if output_report is None:
            run_dir = job.get("run_dir")
            output_name = (job.get("meta") or {}).get("output_filename", "experiment_report_evaluated.json")
            if isinstance(run_dir, str):
                candidate = Path(run_dir) / str(output_name)
                if candidate.exists():
                    output_report = str(candidate)

        return EvalResult(
            status=job.get("status", "queued"),
            output_report=output_report,
            payload=payload,
            log_tail=job_log_tail(job),
        )

    def list_jobs(self, refresh: bool = True) -> list[dict[str, Any]]:
        if refresh:
            return refresh_all_jobs(jobs_path=self.jobs_path)
        return list_jobs(jobs_path=self.jobs_path)

