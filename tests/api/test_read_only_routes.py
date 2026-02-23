from __future__ import annotations

from fastapi.testclient import TestClient

from zugzwang.api import deps
from zugzwang.api.main import create_app
from zugzwang.api.types import (
    BoardStateFrame,
    ConfigTemplate,
    DashboardKpis,
    DashboardTimelinePoint,
    GameMeta,
    GameRecordView,
    ResolvedConfigPreview,
    RunMeta,
    RunProgress,
    RunSummary,
    ValidationResult,
)


class FakeConfigService:
    def list_templates(self) -> list[ConfigTemplate]:
        return [
            ConfigTemplate(name="best_known_start", path="configs/baselines/best_known_start.yaml", category="baselines"),
            ConfigTemplate(name="rag_variants", path="configs/ablations/rag_variants.yaml", category="ablations"),
        ]

    def validate_config(self, config_path: str, overrides=None, model_profile: str | None = None) -> ValidationResult:
        _ = (config_path, overrides, model_profile)
        return ValidationResult(
            ok=True,
            message="Config is valid",
            config_hash="cfg-hash-1",
            resolved_config={"experiment": {"name": "best_known_start"}},
        )

    def resolve_config_preview(self, config_path: str, overrides=None, model_profile: str | None = None) -> ResolvedConfigPreview:
        _ = (config_path, overrides, model_profile)
        return ResolvedConfigPreview(
            config_path="configs/baselines/best_known_start.yaml",
            config_hash="cfg-hash-1",
            run_id="best_known_start-20260222T100000Z-abcdef01",
            scheduled_games=5,
            estimated_total_cost_usd=0.42,
            resolved_config={"experiment": {"name": "best_known_start"}},
        )


class FakeRunService:
    def __init__(self) -> None:
        self._job = {
            "job_id": "job-1",
            "job_type": "run",
            "status": "running",
            "pid": 1234,
            "command": ["python", "-m", "zugzwang.cli", "run"],
            "created_at_utc": "2026-02-22T05:00:00Z",
            "updated_at_utc": "2026-02-22T05:00:01Z",
            "stdout_path": "results/ui_jobs/logs/job-1.stdout.log",
            "stderr_path": "results/ui_jobs/logs/job-1.stderr.log",
            "run_id": "run-1",
            "run_dir": "results/runs/run-1",
            "meta": {},
        }

    def list_jobs(self, refresh: bool = True) -> list[dict[str, object]]:
        return [self._job]

    def get_job(self, job_id: str, refresh: bool = True):
        if job_id == "job-1":
            return self._job
        return None

    def get_run_progress(self, job_id: str) -> RunProgress:
        if job_id != "job-1":
            raise ValueError(f"Unknown job id: {job_id}")
        return RunProgress(
            run_id="run-1",
            status="running",
            games_written=2,
            games_target=5,
            run_dir="results/runs/run-1",
            stopped_due_to_budget=False,
            budget_stop_reason=None,
            latest_report={"completion_rate": 1.0},
            log_tail="tail",
        )


class FakeArtifactService:
    def __init__(self) -> None:
        self._runs = [
            RunMeta(
                run_id="run-1",
                run_dir="results/runs/run-1",
                created_at_utc="2026-02-22T05:00:00Z",
                config_hash="abc123",
                report_exists=True,
                evaluated_report_exists=True,
                inferred_player_color="black",
                inferred_opponent_elo=1200,
                inferred_provider="zai",
                inferred_model="glm-5",
                inferred_model_label="zai / glm-5",
                inferred_config_template="best_known_start",
                inferred_eval_status="evaluated",
                num_games_target=5,
                num_games_valid=5,
                completion_rate=1.0,
                total_cost_usd=1.23,
                elo_estimate=620.0,
                acpl_overall=55.0,
                blunder_rate=0.1,
            ),
            RunMeta(
                run_id="run-2",
                run_dir="results/runs/run-2",
                created_at_utc="2026-02-21T03:00:00Z",
                config_hash="def456",
                report_exists=True,
                evaluated_report_exists=False,
                inferred_player_color="black",
                inferred_provider="openai",
                inferred_model="gpt-5-mini",
                inferred_model_label="openai / gpt-5-mini",
                inferred_config_template="rag_variant",
                inferred_eval_status="needs_eval",
                num_games_target=8,
                num_games_valid=6,
                completion_rate=0.75,
                total_cost_usd=2.5,
            ),
        ]

    def list_runs(self, filters=None) -> list[RunMeta]:
        filters = filters or {}
        items = list(self._runs)

        query = str(filters.get("query", "")).strip().lower()
        if query:
            items = [
                item
                for item in items
                if query in item.run_id.lower()
                or query in (item.inferred_model_label or "").lower()
            ]

        if bool(filters.get("evaluated_only", False)):
            items = [item for item in items if item.evaluated_report_exists]

        provider = str(filters.get("provider", "")).strip().lower()
        if provider:
            items = [item for item in items if (item.inferred_provider or "").lower() == provider]

        model = str(filters.get("model", "")).strip().lower()
        if model:
            items = [item for item in items if (item.inferred_model or "").lower() == model]

        status = str(filters.get("status", "")).strip().lower()
        if status == "evaluated":
            items = [item for item in items if item.evaluated_report_exists]
        elif status == "needs_eval":
            items = [item for item in items if item.report_exists and not item.evaluated_report_exists]
        elif status == "pending_report":
            items = [item for item in items if not item.report_exists]

        date_from = filters.get("date_from")
        if date_from is not None:
            lower = date_from.isoformat()
            items = [item for item in items if (item.created_at_utc or "")[:10] >= lower]

        date_to = filters.get("date_to")
        if date_to is not None:
            upper = date_to.isoformat()
            items = [item for item in items if (item.created_at_utc or "")[:10] <= upper]

        sort_by = str(filters.get("sort_by", "created_at_utc"))
        sort_dir = str(filters.get("sort_dir", "desc")).lower()
        reverse = sort_dir != "asc"
        if sort_by == "total_cost_usd":
            items.sort(key=lambda item: item.total_cost_usd or 0.0, reverse=reverse)
        elif sort_by == "elo_estimate":
            items.sort(key=lambda item: item.elo_estimate or 0.0, reverse=reverse)
        elif sort_by == "acpl_overall":
            items.sort(key=lambda item: item.acpl_overall or 0.0, reverse=reverse)
        elif sort_by == "run_id":
            items.sort(key=lambda item: item.run_id, reverse=reverse)
        else:
            items.sort(key=lambda item: item.created_at_utc or "", reverse=reverse)

        offset = int(filters.get("offset", 0) or 0)
        if offset > 0:
            items = items[offset:]
        limit = filters.get("limit")
        if limit is not None:
            items = items[: int(limit)]
        return items

    def load_run_summary(self, run_dir: str) -> RunSummary:
        if run_dir != "run-1":
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
        run_meta = self.list_runs()[0]
        return RunSummary(
            run_meta=run_meta,
            resolved_config={"experiment": {"name": "best_known_start"}},
            report={"num_games_target": 5},
            evaluated_report=None,
            game_count=2,
        )

    def build_dashboard_kpis(self, timeline_limit: int = 40) -> DashboardKpis:
        runs = self.list_runs({"sort_by": "created_at_utc", "sort_dir": "desc"})
        evaluated = [item for item in runs if item.evaluated_report_exists]
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
            for item in runs[:timeline_limit]
        ]
        return DashboardKpis(
            total_runs=len(runs),
            runs_with_reports=sum(1 for item in runs if item.report_exists),
            evaluated_runs=len(evaluated),
            best_elo=max((item.elo_estimate for item in evaluated if item.elo_estimate is not None), default=None),
            avg_acpl=(
                sum(item.acpl_overall for item in evaluated if item.acpl_overall is not None)
                / max(1, len([item for item in evaluated if item.acpl_overall is not None]))
            )
            if any(item.acpl_overall is not None for item in evaluated)
            else None,
            total_cost_usd=float(sum(item.total_cost_usd or 0.0 for item in runs)),
            last_run_id=runs[0].run_id if runs else None,
            timeline=timeline,
        )

    def list_games(self, run_dir: str) -> list[GameMeta]:
        if run_dir != "run-1":
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
        return [GameMeta(game_number=1, path="results/runs/run-1/games/game_0001.json")]

    def load_game(self, run_dir: str, game_number: int) -> GameRecordView:
        if run_dir != "run-1":
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
        if game_number != 1:
            raise FileNotFoundError(f"Game file not found: game_{game_number:04d}.json")
        return GameRecordView(
            game_number=1,
            result="1-0",
            termination="checkmate",
            duration_seconds=10.0,
            total_cost_usd=0.02,
            total_tokens={"input": 100, "output": 50},
            moves=[{"ply_number": 1, "move_decision": {"move_uci": "e2e4"}}],
        )


class FakeReplayService:
    def build_board_states(self, game_record):
        _ = game_record
        return [
            BoardStateFrame(
                ply_number=0,
                fen="start",
                svg="<svg />",
                move_uci=None,
                move_san=None,
                color=None,
                raw_response=None,
            ),
            BoardStateFrame(
                ply_number=1,
                fen="after",
                svg="<svg />",
                move_uci="e2e4",
                move_san="e4",
                color="white",
                raw_response="e2e4",
            ),
        ]


def _build_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.get_config_service] = lambda: FakeConfigService()
    app.dependency_overrides[deps.get_run_service] = lambda: FakeRunService()
    app.dependency_overrides[deps.get_artifact_service] = lambda: FakeArtifactService()
    app.dependency_overrides[deps.get_replay_service] = lambda: FakeReplayService()
    return TestClient(app)


def test_configs_route_groups_baselines_and_ablations() -> None:
    client = _build_client()
    response = client.get("/api/configs")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["baselines"]) == 1
    assert len(payload["ablations"]) == 1
    assert payload["baselines"][0]["name"] == "best_known_start"

    validate_response = client.post(
        "/api/configs/validate",
        json={"config_path": "configs/baselines/best_known_start.yaml", "overrides": []},
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["ok"] is True
    assert validate_response.json()["config_hash"] == "cfg-hash-1"

    preview_response = client.post(
        "/api/configs/preview",
        json={"config_path": "configs/baselines/best_known_start.yaml", "overrides": []},
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["run_id"].startswith("best_known_start-")

    model_catalog_response = client.get("/api/configs/model-catalog")
    assert model_catalog_response.status_code == 200
    providers = {item["provider"] for item in model_catalog_response.json()}
    assert {"zai", "openai", "anthropic", "google", "grok", "deepseek", "kimi", "minimax"}.issubset(providers)


def test_jobs_routes_return_job_and_progress() -> None:
    client = _build_client()
    jobs_response = client.get("/api/jobs")
    assert jobs_response.status_code == 200
    assert jobs_response.json()[0]["job_id"] == "job-1"

    detail_response = client.get("/api/jobs/job-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "running"

    progress_response = client.get("/api/jobs/job-1/progress")
    assert progress_response.status_code == 200
    assert progress_response.json()["games_written"] == 2

    missing_response = client.get("/api/jobs/missing")
    assert missing_response.status_code == 404


def test_runs_routes_return_summary_games_and_frames() -> None:
    client = _build_client()

    list_response = client.get("/api/runs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["run_id"] == "run-1"

    summary_response = client.get("/api/runs/run-1")
    assert summary_response.status_code == 200
    assert summary_response.json()["game_count"] == 2

    report_response = client.get("/api/runs/run-1/report")
    assert report_response.status_code == 200
    assert report_response.json()["num_games_target"] == 5

    config_response = client.get("/api/runs/run-1/config")
    assert config_response.status_code == 200
    assert config_response.json()["experiment"]["name"] == "best_known_start"

    games_response = client.get("/api/runs/run-1/games")
    assert games_response.status_code == 200
    assert games_response.json()[0]["game_number"] == 1

    game_response = client.get("/api/runs/run-1/games/1")
    assert game_response.status_code == 200
    assert game_response.json()["result"] == "1-0"

    frames_response = client.get("/api/runs/run-1/games/1/frames")
    assert frames_response.status_code == 200
    assert len(frames_response.json()) == 2

    inferred = summary_response.json()
    assert inferred["inferred_model_label"] == "zai / glm-5"
    assert inferred["run_meta"]["inferred_eval_status"] == "evaluated"
    assert inferred["run_meta"]["elo_estimate"] == 620.0

    missing_run_response = client.get("/api/runs/missing")
    assert missing_run_response.status_code == 404


def test_runs_route_supports_extended_filters_sort_and_pagination() -> None:
    client = _build_client()
    response = client.get(
        "/api/runs",
        params={
            "q": "glm-5",
            "provider": "zai",
            "model": "glm-5",
            "status": "evaluated",
            "date_from": "2026-02-20",
            "date_to": "2026-02-23",
            "sort_by": "total_cost_usd",
            "sort_dir": "asc",
            "offset": 0,
            "limit": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["run_id"] == "run-1"
    assert payload[0]["inferred_model_label"] == "zai / glm-5"

    alias_response = client.get("/api/runs", params={"evaluated": "true"})
    assert alias_response.status_code == 200
    assert [item["run_id"] for item in alias_response.json()] == ["run-1"]


def test_dashboard_kpis_route_returns_aggregates() -> None:
    client = _build_client()
    response = client.get("/api/dashboard/kpis", params={"timeline_limit": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 2
    assert payload["evaluated_runs"] == 1
    assert payload["best_elo"] == 620.0
    assert len(payload["timeline"]) == 1
    assert payload["timeline"][0]["run_id"] == "run-1"


def test_env_check_route_exposes_provider_statuses() -> None:
    client = _build_client()
    response = client.get("/api/env-check")
    assert response.status_code == 200
    providers = {item["provider"] for item in response.json()}
    assert {"zai", "openai", "anthropic", "google", "mock", "stockfish"}.issubset(providers)
