from __future__ import annotations

from fastapi.testclient import TestClient

from zugzwang.api import deps
from zugzwang.api.main import create_app


class FakeSchedulerService:
    def __init__(self) -> None:
        self.batch = {
            "batch_id": "batch-1",
            "status": "running",
            "fail_fast": True,
            "dry_run": False,
            "created_at_utc": "2026-02-23T10:00:00Z",
            "updated_at_utc": "2026-02-23T10:00:01Z",
            "steps": [
                {
                    "step_id": "a",
                    "config_path": "configs/baselines/best_known_start.yaml",
                    "mode": "run",
                    "model_profile": None,
                    "overrides": [],
                    "depends_on": [],
                    "status": "running",
                    "message": "started",
                    "job_id": "job-1",
                    "run_id": "run-1",
                    "run_dir": "results/runs/run-1",
                    "started_at_utc": "2026-02-23T10:00:00Z",
                    "finished_at_utc": None,
                    "preview": {
                        "config_hash": "cfg-1",
                        "run_id": "preview-run-1",
                        "scheduled_games": 5,
                        "estimated_total_cost_usd": 1.0,
                    },
                }
            ],
        }

    def create_batch(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return self.batch

    def list_batches(self, limit=50, refresh=True):  # type: ignore[no-untyped-def]
        _ = (limit, refresh)
        return [self.batch]

    def get_batch(self, batch_id, refresh=True):  # type: ignore[no-untyped-def]
        _ = refresh
        if batch_id != self.batch["batch_id"]:
            raise FileNotFoundError(batch_id)
        return self.batch

    def cancel_batch(self, batch_id):  # type: ignore[no-untyped-def]
        if batch_id != self.batch["batch_id"]:
            raise FileNotFoundError(batch_id)
        output = dict(self.batch)
        output["status"] = "canceled"
        return output



def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.get_scheduler_service] = lambda: FakeSchedulerService()
    return TestClient(app)


def test_scheduler_routes_create_list_get_cancel() -> None:
    client = _client()

    create_response = client.post(
        "/api/scheduler/batches",
        json={
            "steps": [
                {
                    "step_id": "a",
                    "config_path": "configs/baselines/best_known_start.yaml",
                    "mode": "run",
                    "depends_on": [],
                    "overrides": [],
                }
            ],
            "fail_fast": True,
            "dry_run": False,
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["batch_id"] == "batch-1"

    list_response = client.get("/api/scheduler/batches")
    assert list_response.status_code == 200
    assert list_response.json()[0]["batch_id"] == "batch-1"

    get_response = client.get("/api/scheduler/batches/batch-1")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "running"

    cancel_response = client.delete("/api/scheduler/batches/batch-1")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "canceled"


def test_scheduler_get_missing_batch_returns_404() -> None:
    client = _client()
    response = client.get("/api/scheduler/batches/missing")
    assert response.status_code == 404
