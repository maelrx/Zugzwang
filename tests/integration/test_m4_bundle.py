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
    EvaluationRunRepository,
    MetricObservationRepository,
)
from zugzwang_runtime.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "experiments" / "chess-move-selection.yaml"
R6_MANIFEST = REPO_ROOT / "experiments" / "pure-search-v1.yaml"


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    ws = Workspace.from_root(tmp_path / "ws", wal_policy="ephemeral")
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
    async def test_each_decision_has_direct_evidence_links(self, workspace: Workspace) -> None:
        run_id = await _run_chess(workspace)
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        step = connection.execute(
            "SELECT observation_artifact_id, decision_trace_artifact_id "
            "FROM steps WHERE episode_id IN (SELECT episode_id FROM episodes WHERE run_id=?)",
            (run_id,),
        ).fetchone()
        assert step is not None
        observation_ref, trace_ref = step
        assert observation_ref and trace_ref
        attempt = connection.execute(
            "SELECT request_artifact_id, response_artifact_id FROM attempts "
            "WHERE step_id IN (SELECT step_id FROM steps WHERE observation_artifact_id=?)",
            (observation_ref,),
        ).fetchone()
        assert attempt is not None
        assert attempt[0] and attempt[1]
        trace_events = connection.execute(
            "SELECT count(*) FROM events WHERE run_id=? AND event_type='step.decided' "
            "AND artifact_refs_json LIKE ?",
            (run_id, f"%{trace_ref}%"),
        ).fetchone()[0]
        assert trace_events == 1
        import json

        services = DurableRunServices(workspace, PluginRegistry())
        trace_artifact = ArtifactRepository(services.database_engine).get(trace_ref)
        assert trace_artifact is not None
        trace_data = json.loads(
            (workspace.objects_dir() / trace_artifact["relative_path"]).read_text(encoding="utf-8")
        )
        assert trace_data["calls"][0]["request_artifact_ref"]
        assert trace_data["artifact_refs"]

    @pytest.mark.asyncio
    async def test_r6_search_is_persisted_and_declared_model_only(
        self, workspace: Workspace
    ) -> None:
        services = DurableRunServices(workspace, PluginRegistry())
        result = await services.start(StartRunCommand(manifest_path=R6_MANIFEST), asyncio.Event())
        assert result.status == "COMPLETED"
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        step = connection.execute(
            "SELECT search_session_id, search_graph_artifact_id, action_json FROM steps "
            "WHERE status='COMMITTED'"
        ).fetchone()
        assert step is not None
        assert step[0] and step[1]
        assert '"action": "e2e4"' in step[2]
        session = connection.execute(
            "SELECT algorithm, namespace, status, stats_json FROM search_sessions "
            "WHERE search_session_id=?",
            (step[0],),
        ).fetchone()
        assert session is not None
        assert session[:3] == ("R6-BatchedTree", "search://", "COMPLETED")
        assert '"branch_nodes_created": 4' in session[3]
        assert (
            connection.execute(
                "SELECT count(*) FROM search_edges WHERE search_session_id=? AND legal=0",
                (step[0],),
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM search_retrieval_events WHERE search_session_id=?",
                (step[0],),
            ).fetchone()[0]
            == 2
        )

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
        assert summary.observations >= 10  # precise scores, move metadata and new analysis fields
        assert "chess.move_class" in summary.metrics
        assert "chess.engine_best_move" in summary.metrics
        connection = sqlite3.connect(workspace.data_dir / "state.db")
        stored = connection.execute(
            "SELECT count(*) FROM metric_observations WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        assert stored == summary.observations
        episode_id = connection.execute(
            "SELECT episode_id FROM metric_observations WHERE run_id=? LIMIT 1", (run_id,)
        ).fetchone()[0]
        assert episode_id is not None
        evaluation_runs = EvaluationRunRepository(services.database_engine).for_run(run_id)
        assert len(evaluation_runs) == 1
        assert evaluation_runs[0]["status"] == "COMPLETED"
        evaluation_run_id = evaluation_runs[0]["evaluation_run_id"]
        import json

        engine_metadata = evaluation_runs[0]["engine_json"]
        if isinstance(engine_metadata, str):
            engine_metadata = json.loads(engine_metadata)
        assert engine_metadata["engine"]["binary"]["binary"] == "fake-engine"
        assert (
            connection.execute(
                "SELECT count(*) FROM metric_observations WHERE evaluation_run_id=? "
                "AND provenance_artifact_id IS NOT NULL",
                (evaluation_run_id,),
            ).fetchone()[0]
            == summary.observations
        )
        assert all(
            row["evaluation_run_id"] == evaluation_run_id
            for row in MetricObservationRepository(services.database_engine).for_run(run_id)
        )
        event_types = [
            row[0]
            for row in connection.execute("SELECT event_type FROM events WHERE run_id=?", (run_id,))
        ]
        assert "evaluation.run.started" in event_types
        assert "evaluation.run.completed" in event_types

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
        assert engine.requests == 2, "cached before/after evaluations must not repeat"


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
        assert (bundle_dir / "evaluation_runs.json").exists()

        second_ws = Workspace.from_root(tmp_path / "ws2", wal_policy="ephemeral")
        second_ws.ensure_layout()
        second_services = DurableRunServices(second_ws, PluginRegistry())
        importer = ImportRunBundleService(
            cas=second_services.cas,
            artifacts=ArtifactRepository(second_services.database_engine),
        )
        result = importer.import_bundle(bundle_dir)
        assert int(result["artifacts_imported"]) >= 1

        # ZGW-0085/#15: importing bytes alone does not reproduce a run —
        # projections are rebuilt from the authoritative event stream, then
        # offline re-evaluation replays the same committed moves.
        rebuild = importer.rebuild_projections(
            bundle_dir,
            runs=second_services.runs,
            episodes=second_services.episodes,
            steps=second_services.steps,
            events=second_services.events,
        )
        assert rebuild["steps"] >= 1
        assert rebuild["episodes"] >= 1

        from zugzwang_runtime.application.evaluation import build_evaluation_steps

        original_steps = build_evaluation_steps(
            run_id=run_id,
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            cas=services.cas,
        )
        rebuilt_steps = build_evaluation_steps(
            run_id=run_id,
            runs=second_services.runs,
            episodes=second_services.episodes,
            steps=second_services.steps,
            cas=second_services.cas,
        )
        assert original_steps, "the source run must have committed model steps"
        assert rebuilt_steps == original_steps, (
            "reconstruction must reproduce exactly the committed (fen, action) sequence"
        )

    @pytest.mark.asyncio
    async def test_rebuilt_run_yields_equivalent_fake_evaluation(
        self, workspace: Workspace, tmp_path
    ) -> None:
        """ZGW-0085/#15 closing path: export -> import into an isolated
        workspace -> rebuild projections -> identical moves -> equivalent
        fake evaluation, without any access to the original workspace."""
        from zgw_eval_stockfish.evaluator import StockfishEvaluator
        from zgw_eval_stockfish.uci import FakeUciEngine

        from zugzwang_runtime.application.evaluation import build_evaluation_steps

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
        bundle_dir = exporter.export(run_id, tmp_path / "bundle-eval")

        second_ws = Workspace.from_root(tmp_path / "ws-eval", wal_policy="ephemeral")
        second_ws.ensure_layout()
        second_services = DurableRunServices(second_ws, PluginRegistry())
        importer = ImportRunBundleService(
            cas=second_services.cas,
            artifacts=ArtifactRepository(second_services.database_engine),
        )
        importer.import_bundle(bundle_dir)
        importer.rebuild_projections(
            bundle_dir,
            runs=second_services.runs,
            episodes=second_services.episodes,
            steps=second_services.steps,
            events=second_services.events,
        )

        assert build_evaluation_steps(
            run_id=run_id,
            runs=second_services.runs,
            episodes=second_services.episodes,
            steps=second_services.steps,
            cas=second_services.cas,
        ) == build_evaluation_steps(
            run_id=run_id,
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            cas=services.cas,
        )

        evaluator = StockfishEvaluator(FakeUciEngine())
        evaluate = EvaluateRunService(
            runs=services.runs,
            episodes=services.episodes,
            steps=services.steps,
            metrics=MetricObservationRepository(services.database_engine),
            cas=services.cas,
        )
        original_summary = await evaluate.evaluate(
            run_id, evaluator, evaluator_id="evaluator.stockfish"
        )
        rebuilt_summary = await EvaluateRunService(
            runs=second_services.runs,
            episodes=second_services.episodes,
            steps=second_services.steps,
            metrics=MetricObservationRepository(second_services.database_engine),
            cas=second_services.cas,
        ).evaluate(run_id, StockfishEvaluator(FakeUciEngine()), evaluator_id="evaluator.stockfish")

        assert original_summary.observations == rebuilt_summary.observations > 0
        assert original_summary.metrics == rebuilt_summary.metrics, (
            "the same evaluator over the reconstructed moves must agree exactly"
        )

    @pytest.mark.asyncio
    async def test_reconstruction_detects_truncated_event_stream(
        self, workspace: Workspace, tmp_path
    ) -> None:
        """Deliberate mutation: dropping the final commit must change what the
        reconstruction replays, proving the equality assertions can fail."""
        from zugzwang_runtime.application.evaluation import build_evaluation_steps

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
        bundle_dir = exporter.export(run_id, tmp_path / "bundle-trunc")

        def _rebuild(bd: Path, ws_root: str) -> list[dict]:
            ws = Workspace.from_root(tmp_path / ws_root, wal_policy="ephemeral")
            ws.ensure_layout()
            ws_services = DurableRunServices(ws, PluginRegistry())
            imp = ImportRunBundleService(
                cas=ws_services.cas,
                artifacts=ArtifactRepository(ws_services.database_engine),
            )
            imp.import_bundle(bd)
            imp.rebuild_projections(
                bd,
                runs=ws_services.runs,
                episodes=ws_services.episodes,
                steps=ws_services.steps,
                events=ws_services.events,
            )
            return build_evaluation_steps(
                run_id=run_id,
                runs=ws_services.runs,
                episodes=ws_services.episodes,
                steps=ws_services.steps,
                cas=ws_services.cas,
            )

        full = _rebuild(bundle_dir, "ws-trunc-full")
        truncated_path = tmp_path / "bundle-trunc-cut"
        exporter.export(run_id, truncated_path)
        committed_lines = [
            line
            for line in (truncated_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if '"step.committed"' in line
        ]
        events_text = (truncated_path / "events.jsonl").read_text(encoding="utf-8")
        (truncated_path / "events.jsonl").write_text(
            events_text.replace(committed_lines[-1] + "\n", ""), encoding="utf-8"
        )
        # the checksum manifest no longer matches; rewrite it for the mutation
        import hashlib

        lines = []
        for path in sorted(truncated_path.rglob("*")):
            if path.is_file() and path.name != "checksums.sha256":
                rel = path.relative_to(truncated_path).as_posix()
                lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel}")
        (truncated_path / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

        cut = _rebuild(truncated_path, "ws-trunc-cut")
        assert full, "baseline reconstruction must have committed steps"
        assert len(cut) < len(full), (
            "truncating the last committed move must be visible to the replay"
        )

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
        second_ws = Workspace.from_root(tmp_path / "ws3", wal_policy="ephemeral")
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


@pytest.mark.integration
def test_readonly_export_never_touches_source(tmp_path: Path) -> None:
    """ZGW-0101: the exporter opens the SOURCE read-only — header, PRAGMAs,
    content and schema are identical before/after; writes are refused."""
    import sqlite3

    import sqlalchemy as sa

    from zugzwang_runtime.persistence.database import Database

    source = tmp_path / "source.db"
    conn = sqlite3.connect(str(source))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t VALUES (1,'hello')")
    conn.commit()
    # Settle the WAL into the main file and remove sidecars, so any
    # exporter-created -wal/-shm file is detectable below.
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    for sidecar in (source.with_suffix(".db-wal"), source.with_suffix(".db-shm")):
        sidecar.unlink(missing_ok=True)
    before = {
        "journal": conn.execute("PRAGMA journal_mode").fetchone()[0],
        "synchronous": conn.execute("PRAGMA synchronous").fetchone()[0],
        "rows": conn.execute("SELECT * FROM t").fetchall(),
        "schema": conn.execute("SELECT sql FROM sqlite_master WHERE name='t'").fetchone()[0],
        "size": source.stat().st_size,
        "bytes": source.read_bytes(),
    }
    conn.close()

    assert before["journal"] == "wal", "precondition: source is a WAL database"
    database = Database(source, wal_policy="enforce", read_only=True)
    engine = database.open()
    with engine.connect() as read:
        assert read.execute(sa.text("SELECT v FROM t")).fetchone()[0] == "hello"
    with (
        pytest.raises(Exception, match=r"(?i)read.?only|attempt to write"),
        engine.begin() as write,
    ):
        write.execute(sa.text("INSERT INTO t VALUES (2,'hack')"))
    database.close()

    conn = sqlite3.connect(str(source))
    after = {
        "journal": conn.execute("PRAGMA journal_mode").fetchone()[0],
        "synchronous": conn.execute("PRAGMA synchronous").fetchone()[0],
        "rows": conn.execute("SELECT * FROM t").fetchall(),
        "schema": conn.execute("SELECT sql FROM sqlite_master WHERE name='t'").fetchone()[0],
    }
    conn.close()
    assert after == {k: before[k] for k in after}
    assert source.stat().st_size == before["size"], "source file byte-identical"
    assert not source.with_suffix(".db-wal").exists(), "no WAL sidecar created"
    assert not source.with_suffix(".db-shm").exists(), "no SHM sidecar created"
    assert source.read_bytes() == before["bytes"]
