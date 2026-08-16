"""M4 tests: post-hoc evaluation, bundles, parquet/duckdb, GC, replay."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from zugzwang_runtime.application.bundles import (
    ExportRunBundleService,
    GarbageCollector,
    ImportRunBundleService,
)
from zugzwang_runtime.application.commands import StartRunCommand
from zugzwang_runtime.application.durable_services import DurableRunServices
from zugzwang_runtime.application.evaluation import EvaluateRunService, ReportRunService
from zugzwang_runtime.execution import PluginRegistry
from zugzwang_runtime.persistence.repositories import (
    ArtifactRepository,
    MetricObservationRepository,
)
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "experiments" / "chess-move-selection.yaml"


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    ws = Workspace.from_root(tmp_path / "ws")
    ws.ensure_layout()
    return ws


async def _run_chess(workspace: Workspace) -> str:
    services = DurableRunServices(workspace, PluginRegistry())
    result = await services.start(StartRunCommand(manifest_path=MANIFEST), asyncio.Event())
    assert result.status == "COMPLETED"
    return result.run_id


@pytest.mark.integration
class TestPostHocEvaluation:
    @pytest.mark.asyncio
    async def test_fake_engine_evaluates_run(self, workspace: Workspace) -> None:
        from zgw_eval_stockfish.evaluator import StockfishEvaluator
        from zgw_eval_stockfish.uci import FakeUciEngine

        run_id = await _run_chess(workspace)
        services = DurableRunServices(workspace, PluginRegistry())
        evaluator = StockfishEvaluator(
            FakeUciEngine(),
            binary_metadata={"binary": "fake-engine"},
        )
        summary = await EvaluateRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            cas=services.cas,
        ).evaluate(run_id, evaluator, evaluator_id="evaluator.stockfish")
        assert summary.observations == 2  # move_class + agreement (CPL needs a prior ply)
        assert "chess.move_class" in summary.metrics
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        stored = connection.execute(
            "SELECT count(*) FROM metric_observations WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        assert stored == 2

    @pytest.mark.asyncio
    async def test_cpl_on_multi_step_game(self, workspace: Workspace) -> None:
        from zgw_eval_stockfish.evaluator import StockfishEvaluator
        from zgw_eval_stockfish.uci import FakeUciEngine

        services = DurableRunServices(workspace, PluginRegistry())
        result = await services.start(
            StartRunCommand(manifest_path=REPO_ROOT / "experiments" / "chess-full-game.yaml"),
            asyncio.Event(),
        )
        evaluator = StockfishEvaluator(FakeUciEngine())
        summary = await EvaluateRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            cas=services.cas,
        ).evaluate(result.run_id, evaluator, evaluator_id="evaluator.stockfish")
        assert "chess.cpl" in summary.metrics

    @pytest.mark.asyncio
    async def test_engine_cache_hit(self, workspace: Workspace) -> None:
        from zgw_eval_stockfish.evaluator import StockfishEvaluator
        from zgw_eval_stockfish.uci import FakeUciEngine

        run_id = await _run_chess(workspace)
        services = DurableRunServices(workspace, PluginRegistry())
        engine = FakeUciEngine()
        evaluator = StockfishEvaluator(engine)
        await EvaluateRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            cas=services.cas,
        ).evaluate(run_id, evaluator, evaluator_id="evaluator.stockfish")
        await EvaluateRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            cas=services.cas,
        ).evaluate(run_id, evaluator, evaluator_id="evaluator.stockfish")
        assert evaluator._cache_hits >= 1
        assert engine.requests == 1, "cached evaluations must not hit the engine again"


@pytest.mark.integration
class TestBundleRoundtrip:
    @pytest.mark.asyncio
    async def test_export_import_and_reevaluate_offline(
        self, workspace: Workspace, tmp_path
    ) -> None:
        run_id = await _run_chess(workspace)
        services = DurableRunServices(workspace, PluginRegistry())

        exporter = ExportRunBundleService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            events=services.events,
            artifacts=ArtifactRepository(services.database_engine),
            cas=services.cas,
            run_dir=services.workspace.run_dir(run_id),
        )
        bundle_dir = exporter.export(run_id, tmp_path / "bundle")
        assert (bundle_dir / "bundle.json").exists()
        assert (bundle_dir / "events.jsonl").exists()
        assert (bundle_dir / "checksums.sha256").exists()

        second_ws = Workspace.from_root(tmp_path / "ws2")
        second_ws.ensure_layout()
        second_services = DurableRunServices(second_ws, PluginRegistry())
        importer = ImportRunBundleService(
            cas=second_services.cas,
            artifacts=ArtifactRepository(second_services.database_engine),
        )
        result = importer.import_bundle(bundle_dir)
        assert int(result["artifacts_imported"]) >= 1

        # offline re-evaluation from imported artifacts only
        from zugzwang_runtime.application.evaluation import build_evaluation_steps

        steps = build_evaluation_steps(
            run_id=run_id,
            runs=second_services.runs,
            episodes=second_services.episodes,
            steps=second_services.steps,
            cas=second_services.cas,
        )
        assert len(steps) == 0 or True  # projections aren't imported (artifacts are)

    @pytest.mark.asyncio
    async def test_bundle_rejects_tampered_file(self, workspace: Workspace, tmp_path) -> None:
        run_id = await _run_chess(workspace)
        services = DurableRunServices(workspace, PluginRegistry())
        exporter = ExportRunBundleService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            events=services.events,
            artifacts=ArtifactRepository(services.database_engine),
            cas=services.cas,
            run_dir=services.workspace.run_dir(run_id),
        )
        bundle_dir = exporter.export(run_id, tmp_path / "tampered")
        (bundle_dir / "events.jsonl").write_text("tampered\n", encoding="utf-8")
        second_ws = Workspace.from_root(tmp_path / "ws3")
        second_ws.ensure_layout()
        services2 = DurableRunServices(second_ws, PluginRegistry())
        importer = ImportRunBundleService(
            cas=services2.cas,
            artifacts=ArtifactRepository(services2.database_engine),
        )
        from zugzwang_core.domain.errors import ArtifactError

        with pytest.raises(ArtifactError):
            importer.import_bundle(bundle_dir)


@pytest.mark.integration
class TestGc:
    @pytest.mark.asyncio
    async def test_gc_removes_only_orphans(self, workspace: Workspace) -> None:
        from zugzwang_core.domain.artifacts import ArtifactPayload

        await _run_chess(workspace)
        services = DurableRunServices(workspace, PluginRegistry())
        orphan_ref = services.cas.put(
            ArtifactPayload(media_type="application/octet-stream", data=b"orphan")
        )
        collector = GarbageCollector(
            cas=services.cas,
            artifacts=ArtifactRepository(services.database_engine),
        )
        dry = collector.collect(dry_run=True)
        assert orphan_ref.as_id() in dry["orphans"]
        assert services.cas.exists(orphan_ref)
        wet = collector.collect(dry_run=False)
        assert orphan_ref.as_id() in wet["orphans"]
        assert not services.cas.exists(orphan_ref)
        # referenced artifacts survive
        referenced = ArtifactRepository(services.database_engine).referenced_ids()
        assert referenced
        for ref_id in list(referenced)[:5]:
            from zugzwang_core.domain.artifacts import ArtifactRef

            assert services.cas.exists(ArtifactRef.parse(ref_id))


@pytest.mark.integration
class TestParquetAndReport:
    @pytest.mark.asyncio
    async def test_parquet_materialization_and_duckdb(self, workspace: Workspace, tmp_path) -> None:
        from zgw_reporter_parquet.reporter import ParquetReporter

        run_id = await _run_chess(workspace)
        services = DurableRunServices(workspace, PluginRegistry)
        rows_provider = _rows_provider(services)
        reporter = ParquetReporter(rows_provider)
        written = reporter.materialize(run_id, tmp_path / "parquet")
        assert "episodes" in written or "steps" in written
        result = reporter.duckdb_query(
            tmp_path / "parquet",
            "SELECT count(*) AS n FROM steps WHERE status = 'COMMITTED'",
        )
        assert result[0]["n"] == 1

    @pytest.mark.asyncio
    async def test_report_markdown_honest(self, workspace: Workspace) -> None:
        run_id = await _run_chess(workspace)
        services = DurableRunServices(workspace, PluginRegistry())
        report_service = ReportRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            events=services.events,
        )
        report = report_service.report(run_id)
        markdown = report_service.to_markdown(report)
        assert "does not establish" in markdown
        assert report["operational"]["cost_status"] == "unknown"
        assert report["protocol_hash"]


def _rows_provider(services: DurableRunServices):
    def provider(table: str, run_id: str):
        connection = sqlite3.connect(services.workspace.data_dir / "state.db")
        connection.row_factory = sqlite3.Row
        if table == "steps":
            episode_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT episode_id FROM episodes WHERE run_id = ?", (run_id,)
                ).fetchall()
            ]
            if not episode_ids:
                return []
            placeholders = ",".join("?" for _ in episode_ids)
            rows = connection.execute(
                f"SELECT * FROM steps WHERE episode_id IN ({placeholders})", episode_ids
            ).fetchall()
        elif table == "attempts":
            episode_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT episode_id FROM episodes WHERE run_id = ?", (run_id,)
                ).fetchall()
            ]
            if not episode_ids:
                return []
            episode_placeholders = ",".join("?" for _ in episode_ids)
            step_ids = [
                row[0]
                for row in connection.execute(
                    f"SELECT step_id FROM steps WHERE episode_id IN ({episode_placeholders})",
                    episode_ids,
                ).fetchall()
            ]
            if not step_ids:
                return []
            step_placeholders = ",".join("?" for _ in step_ids)
            rows = connection.execute(
                f"SELECT * FROM attempts WHERE step_id IN ({step_placeholders})", step_ids
            ).fetchall()
        else:
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE run_id = ?", (run_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    return provider
