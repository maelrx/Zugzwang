"""M5 tests: security, doctor, SBOM, upcasters, tool broker, fault edges."""

from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang_core.domain.errors import SecurityError, ToolNotAllowedError
from zugzwang_runtime.application.sbom import export_cyclonedx
from zugzwang_runtime.execution.tool_broker import ToolBroker
from zugzwang_runtime.execution.upcasters import Upcaster, UpcasterRegistry
from zugzwang_runtime.security import SecretRef, apply_redaction, resolve_secret

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
class TestRedaction:
    def test_env_ref_roundtrip(self, monkeypatch) -> None:
        monkeypatch.setenv("ZGW_TEST_KEY", "topsecret")
        assert resolve_secret("env:ZGW_TEST_KEY") == "topsecret"
        assert str(SecretRef.parse("env:ZGW_TEST_KEY")) == "env:ZGW_TEST_KEY"

    def test_missing_env_ref_raises(self) -> None:
        with pytest.raises(SecurityError):
            resolve_secret("env:ZGW_DOES_NOT_EXIST_12345")

    def test_literal_secret_rejected(self) -> None:
        with pytest.raises(SecurityError):
            resolve_secret("literal-secret")

    def test_standard_redacts_credential_fields(self) -> None:
        payload = {
            "model": "m",
            "headers": {"authorization": "Bearer abc123"},
            "api_key": "sk-secret",
            "safe": "keep me",
        }
        redacted = apply_redaction("standard", payload)
        assert redacted["headers"]["authorization"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["safe"] == "keep me"

    def test_strict_hashes_text(self) -> None:
        payload = {"prompt": "a long prompt that must not be retained verbatim"}
        redacted = apply_redaction("strict", payload)
        assert redacted["prompt"].startswith("sha256:")
        assert "must not be retained" not in str(redacted)

    def test_none_policy_keeps_everything(self) -> None:
        payload = {"secret": "value"}
        assert apply_redaction("none", payload) == payload


@pytest.mark.unit
class TestToolBroker:
    async def test_allowlist_gates_dispatch(self) -> None:
        from zugzwang_core.domain.assistance import AssistanceImpact, HClass
        from zugzwang_core.ports.tool import ToolContext, ToolDescriptor, ToolResult

        class DummyTool:
            @property
            def descriptor(self) -> ToolDescriptor:
                return ToolDescriptor(
                    name="dummy",
                    description="dummy tool",
                    assistance_impact=AssistanceImpact(h=HClass.H1, source="rules_check"),
                    source_of_truth="environment",
                )

            async def invoke(self, arguments, context):
                return ToolResult(data={"ok": True})

        broker = ToolBroker()
        broker.register(DummyTool())
        with pytest.raises(ToolNotAllowedError):
            await broker.invoke(
                "dummy",
                {},
                ToolContext(run_id="run_x", episode_id="ep_x", step_id="stp_x"),
            )
        broker.allow("dummy")
        result = await broker.invoke(
            "dummy",
            {},
            ToolContext(run_id="run_x", episode_id="ep_x", step_id="stp_x"),
        )
        assert result.data == {"ok": True}
        assert broker.allowlisted == ("dummy",)

    def test_unknown_tool_rejected(self) -> None:
        broker = ToolBroker()
        assert broker.definitions() == []
        with pytest.raises(ToolNotAllowedError):
            broker.allow("ghost")


@pytest.mark.unit
class TestUpcasters:
    def test_upcast_chain(self) -> None:
        from zugzwang_core.domain.events import EventContext, EventEnvelope

        registry = UpcasterRegistry()
        registry.register(
            Upcaster(
                event_type="provider.call.completed",
                from_version=1,
                to_version=2,
                transform=lambda payload: {**payload, "upcasted": True},
            )
        )
        event = EventEnvelope.create(
            event_type="provider.call.completed",
            payload={"usage": {"input_tokens": 1}},
            stream_type="step",
            stream_id="stp_x123456789012345678",
            sequence=0,
            context=EventContext(run_id="run_x12345678901234567"),
        )
        upcasted = registry.upcast(event)
        assert upcasted.event_version == 2
        assert upcasted.payload["upcasted"] is True
        assert event.event_version == 1, "original must never be rewritten"


@pytest.mark.unit
class TestSbom:
    def test_cyclonedx_from_lockfile(self) -> None:
        lock = REPO_ROOT / "uv.lock"
        bom = export_cyclonedx(lock, REPO_ROOT)
        assert bom["bomFormat"] == "CycloneDX"
        assert bom["specVersion"] == "1.5"
        assert len(bom["components"]) > 20
        names = {c["name"] for c in bom["components"]}
        assert "pydantic" in names
        assert "sqlalchemy" in names


@pytest.mark.fault
class TestEngineHang:
    @pytest.mark.asyncio
    async def test_fake_engine_hang_raises_typed_error(self) -> None:
        from zgw_eval_stockfish.evaluator import StockfishEvaluator
        from zgw_eval_stockfish.uci import FakeUciEngine

        from zugzwang_core.domain.errors import EngineError
        from zugzwang_core.ports.evaluator import EvaluationContext

        evaluator = StockfishEvaluator(FakeUciEngine(hang=True))
        with pytest.raises(EngineError):
            await evaluator.evaluate(
                EvaluationContext(
                    run_id="run_x",
                    evaluator_config={
                        "steps": [
                            {
                                "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                                "action": "e2e4",
                                "side_to_move": "white",
                                "moves": [],
                            }
                        ]
                    },
                )
            )


@pytest.mark.fault
class TestWriterBackpressure:
    @pytest.mark.asyncio
    async def test_full_queue_raises_typed_error(self, tmp_path) -> None:
        from zugzwang_core.domain.errors import PersistenceError
        from zugzwang_runtime.persistence.database import Database
        from zugzwang_runtime.persistence.event_sink import PersistentEventSink
        from zugzwang_runtime.persistence.repositories import (
            ArtifactRepository,
            AttemptRepository,
            CheckpointRepository,
            EpisodeRepository,
            EventRepository,
            MetricObservationRepository,
            RunRepository,
            SchemaManager,
            StepRepository,
        )
        from zugzwang_runtime.persistence.writer import PersistenceWriter
        from zugzwang_runtime.workspace import Workspace

        ws = Workspace.from_root(tmp_path / "ws", wal_policy="ephemeral")
        ws.ensure_layout()
        db = Database(ws.data_dir / "state.db", wal_policy="ephemeral")
        engine = db.open()
        SchemaManager(engine).upgrade()
        writer = PersistenceWriter(
            runs=RunRepository(engine),
            episodes=EpisodeRepository(engine),
            steps=StepRepository(engine),
            attempts=AttemptRepository(engine),
            events=EventRepository(engine),
            metrics=MetricObservationRepository(engine),
            checkpoints=CheckpointRepository(engine),
            artifacts_repo=ArtifactRepository(engine),
            queue_size=1,
        )
        # writer never started: queue of size 1 fills immediately
        sink = PersistentEventSink(EventRepository(engine), writer)
        from zugzwang_core.domain.events import EventContext, EventEnvelope

        envelope = EventEnvelope.create(
            event_type="run.started",
            payload={},
            stream_type="run",
            stream_id="run_x",
            sequence=0,
            context=EventContext(run_id="run_x"),
        )
        sink.append(envelope)
        with pytest.raises(PersistenceError):
            sink.append(envelope.model_copy(update={"event_id": "evt_other123456789012345"}))
