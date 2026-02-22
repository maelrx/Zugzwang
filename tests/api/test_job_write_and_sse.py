from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from zugzwang.api import deps
from zugzwang.api.main import create_app
from zugzwang.api.types import CancelResult, JobHandle


class FakeRunService:
    def __init__(self, stdout_path: Path, stderr_path: Path) -> None:
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path
        self._log_calls = 0

    def start_run(self, config_path: str, model_profile: str | None = None, overrides=None, mode: str = "run") -> JobHandle:
        _ = (config_path, model_profile, overrides)
        job_id = "job-run" if mode == "run" else "job-play"
        return JobHandle(
            job_id=job_id,
            job_type="run" if mode == "run" else "play",
            status="running",
            pid=111,
            command=["python", "-m", "zugzwang.cli", mode],
            created_at_utc="2026-02-22T05:00:00Z",
            stdout_path=str(self.stdout_path),
            stderr_path=str(self.stderr_path),
            run_id="run-1",
            run_dir="results/runs/run-1",
            meta={},
        )

    def cancel_run(self, job_id: str) -> CancelResult:
        return CancelResult(ok=True, message=f"canceled {job_id}", status="canceled")

    def get_job(self, job_id: str, refresh: bool = True):
        _ = refresh
        if job_id != "job-log":
            return None
        self._log_calls += 1
        status = "completed" if self._log_calls >= 2 else "running"
        return {
            "job_id": job_id,
            "job_type": "run",
            "status": status,
            "pid": 123,
            "command": ["python", "-m", "zugzwang.cli", "run"],
            "created_at_utc": "2026-02-22T05:00:00Z",
            "stdout_path": str(self.stdout_path),
            "stderr_path": str(self.stderr_path),
            "run_id": "run-1",
            "run_dir": "results/runs/run-1",
            "meta": {},
        }


class FakeEvaluationService:
    def start_evaluation(
        self,
        run_dir: str,
        player_color: str = "black",
        opponent_elo: float | None = None,
        output_filename: str = "experiment_report_evaluated.json",
    ) -> JobHandle:
        _ = (run_dir, player_color, opponent_elo, output_filename)
        return JobHandle(
            job_id="job-eval",
            job_type="evaluate",
            status="running",
            pid=222,
            command=["python", "-m", "zugzwang.cli", "evaluate"],
            created_at_utc="2026-02-22T05:00:00Z",
            stdout_path="results/ui_jobs/logs/job-eval.stdout.log",
            stderr_path="results/ui_jobs/logs/job-eval.stderr.log",
            run_id=None,
            run_dir="results/runs/run-1",
            meta={},
        )


def _build_client(tmp_path: Path) -> TestClient:
    stdout_path = tmp_path / "job.stdout.log"
    stderr_path = tmp_path / "job.stderr.log"
    stdout_path.write_text("line-out-1\n", encoding="utf-8")
    stderr_path.write_text("line-err-1\n", encoding="utf-8")

    app = create_app()
    app.dependency_overrides[deps.get_run_service] = lambda: FakeRunService(stdout_path=stdout_path, stderr_path=stderr_path)
    app.dependency_overrides[deps.get_evaluation_service] = lambda: FakeEvaluationService()
    return TestClient(app)


def test_job_write_routes_run_play_evaluate_and_cancel(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    run_response = client.post(
        "/api/jobs/run",
        json={"config_path": "configs/baselines/best_known_start.yaml", "overrides": []},
    )
    assert run_response.status_code == 200
    assert run_response.json()["job_id"] == "job-run"

    play_response = client.post(
        "/api/jobs/play",
        json={"config_path": "configs/baselines/best_known_start.yaml", "overrides": []},
    )
    assert play_response.status_code == 200
    assert play_response.json()["job_id"] == "job-play"

    eval_response = client.post(
        "/api/jobs/evaluate",
        json={"run_dir": "results/runs/run-1", "player_color": "black"},
    )
    assert eval_response.status_code == 200
    assert eval_response.json()["job_id"] == "job-eval"

    cancel_response = client.delete("/api/jobs/job-run")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["ok"] is True


def test_job_logs_sse_streams_stdout_stderr_and_done(tmp_path: Path) -> None:
    client = _build_client(tmp_path)

    chunks: list[str] = []
    with client.stream("GET", "/api/jobs/job-log/logs") as response:
        assert response.status_code == 200
        for chunk in response.iter_text():
            chunks.append(chunk)
            if "event: done" in "".join(chunks):
                break

    output = "".join(chunks)
    assert "event: stdout" in output
    assert "line-out-1" in output
    assert "event: stderr" in output
    assert "line-err-1" in output
    assert "event: done" in output


def test_job_logs_unknown_job_returns_404(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    response = client.get("/api/jobs/missing/logs")
    assert response.status_code == 404
