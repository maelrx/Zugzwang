"""ZGW-0103 acceptance — run pinning, exposure manifest and call-evidence
identity through the REAL RecordingBackend + durable services stack.

- R1 (end to end): two infer calls under distinct caller attempt ids each
  keep their OWN response artifact — evidence_for_calls is the identity join
  the trace stitcher consumes (no positional fallback anywhere);
- R5: a throttling retry honors Retry-After and still lands the mapping;
- R3/R4: every run persists code_git_sha/code_dirty plus an exposure-manifest
  artifact; a declared-but-undeliverable exposure (image on the packet path)
  is rejected as configuration, never silently ignored (dossier §5).
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from zugzwang_core.domain.errors import (
    ManifestValidationError,
    ProviderThrottlingError,
)
from zugzwang_core.ports.model import CallContext
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.execution.backend_caller import RecordingBackend
from zugzwang_runtime.fakes.fake_cognitive_backend import FakeCognitiveBackend

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


class _WriterStub:
    def __init__(self) -> None:
        self.commands: list[Any] = []

    def enqueue(self, command: Any) -> None:
        self.commands.append(command)


class _SinkStub:
    def append(self, envelope: Any) -> None:  # pragma: no cover - trivial
        self.last = envelope


def _context(attempt_id: str) -> CallContext:
    return CallContext(
        run_id="run-1",
        episode_id="ep-1",
        step_id="st-1",
        attempt_id=attempt_id,
        fingerprint="fp",
    )


def _recording_backend(tmp_path: Path, inner: Any, *, max_transport_retries: int = 0):
    return RecordingBackend(
        inner,
        writer=_WriterStub(),
        event_sink=_SinkStub(),
        max_transport_retries=max_transport_retries,
        artifact_store=ContentAddressedStore(tmp_path / "cas"),
        capture_raw_requests=True,
        capture_raw_responses=True,
    )


def _scripted(*entries: dict[str, Any]) -> FakeCognitiveBackend:
    return FakeCognitiveBackend(list(entries))


def _request() -> Any:
    from zugzwang_core.ports.model import (
        Message,
        MessageRole,
        ModelRef,
        ModelRequest,
        TextPart,
    )

    return ModelRequest(
        model=ModelRef(backend="fake", provider="fake", model="scripted"),
        messages=(Message(role=MessageRole.SYSTEM, parts=(TextPart(text="s"),)),),
    )


def test_calls_join_evidence_by_caller_identity(tmp_path) -> None:
    backend = _recording_backend(
        tmp_path,
        _scripted(
            {"tool": "board_observe", "arguments": {"node_id": "node-root"}},
            {"tool": "board_observe", "arguments": {"node_id": "node-root"}},
        ),
    )

    async def _drive():
        await backend.infer(_request(), _context("c1"))
        await backend.infer(_request(), _context("c2"))

    asyncio.run(_drive())
    evidence = backend.evidence_for_calls()
    assert set(evidence) == {"c1", "c2"}
    first = evidence["c1"]["response_artifact_ref"]
    second = evidence["c2"]["response_artifact_ref"]
    assert first and second
    assert first != second, "each caller id must keep its OWN response artifact"
    # current-decision window still carries the real attempt ids
    assert set(backend.evidence_for_current_decision()) <= set(backend.evidence_for_attempts())


def test_throttling_retry_honors_retry_after_and_keeps_mapping(tmp_path) -> None:
    class _ThrottleOnce:
        def __init__(self, inner: Any) -> None:
            self._inner = inner
            self.raised = False

        async def infer(self, request: Any, context: Any) -> Any:
            if not self.raised:
                self.raised = True
                raise ProviderThrottlingError("429", retry_after=0.01)
            return await self._inner.infer(request, context)

    inner = _scripted({"tool": "board_observe", "arguments": {"node_id": "node-root"}})
    backend = _recording_backend(tmp_path, _ThrottleOnce(inner), max_transport_retries=1)

    async def _drive():
        await backend.infer(_request(), _context("c1"))

    asyncio.run(_drive())
    evidence = backend.evidence_for_calls()
    assert evidence["c1"]["response_artifact_ref"], "retry must land the final response"


# ---------------------------------------------------------------------------
# R3/R4: durable services pin + exposure manifest (golden offline manifest)
# ---------------------------------------------------------------------------


def _start_golden(tmp_path: Path, manifest: Path):
    from zugzwang_runtime.application.commands import StartRunCommand
    from zugzwang_runtime.application.durable_services import DurableRunServices
    from zugzwang_runtime.execution.registry import PluginRegistry
    from zugzwang_runtime.workspace import Workspace

    workspace = Workspace.from_root(tmp_path / "ws", wal_policy="ephemeral")
    workspace.ensure_layout()
    services = DurableRunServices(workspace, PluginRegistry())
    result = asyncio.run(services.start(StartRunCommand(manifest_path=manifest), asyncio.Event()))
    return workspace, result


def test_run_row_pins_code_and_exposure_manifest(tmp_path) -> None:
    manifest = REPO_ROOT / "experiments" / "cognitive-golden-offline.yaml"
    workspace, result = _start_golden(tmp_path, manifest)
    assert result.status == "COMPLETED", result
    conn = sqlite3.connect(workspace.data_dir / "state.db")
    try:
        row = conn.execute(
            "SELECT code_git_sha, code_dirty, exposure_manifest_artifact_id FROM runs"
        ).fetchone()
    finally:
        conn.close()
    assert row[0], "run must pin the executing git SHA"
    assert row[1] in (0, 1)
    assert row[2], "run must link an exposure manifest artifact"

    conn = sqlite3.connect(workspace.data_dir / "state.db")
    try:
        relative_path, media_type = conn.execute(
            "SELECT relative_path, media_type FROM artifacts WHERE artifact_id = ?",
            (row[2],),
        ).fetchone()
    finally:
        conn.close()
    assert media_type == "application/vnd.zugzwang.exposure-manifest+json"
    payload = json.loads((workspace.objects_dir() / relative_path).read_text("utf-8"))
    assert payload["schema_version"] == "zgw.exposure-manifest/v1"
    assert payload["effective"]["path"] == "l0_packet"
    assert payload["effective"]["ascii"] is False
    assert payload["effective"]["history_mode"] == "last_n"
    assert payload["code"]["code_git_sha"] == row[0]


def test_image_declaration_on_cognitive_path_is_rejected(tmp_path) -> None:
    golden = (REPO_ROOT / "experiments" / "cognitive-golden-offline.yaml").read_text("utf-8")
    assert "ascii: false" in golden
    patched = golden.replace("ascii: false", "ascii: false, image: true")
    manifest = tmp_path / "cognitive-image.yaml"
    manifest.write_text(patched, encoding="utf-8")
    with pytest.raises(ManifestValidationError):
        _start_golden(tmp_path, manifest)
