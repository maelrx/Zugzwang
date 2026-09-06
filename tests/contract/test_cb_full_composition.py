"""ZGW-0101 — full composition: adapter → loop → broker → transcript (T3).

Offline via httpx.MockTransport (ADR-031): a REAL OpenAiCompatibleBackend
drives the productive CognitiveLoop over a real DecisionSession, with canned
provider responses. Proven here, at the productive path (not test helpers):

- TEST-026: the provider's ORIGINAL tool_call ids survive into
  ``cb_tool_operations.provider_tool_call_id`` and the envelope meta;
- TEST-027 (route equivalence): chat-completions and Responses profiles have
  the same semantic effect through the productive loop, hitting different
  wire endpoints;
- capability gate through ``infer``: a RecordingBackend refusal never
  touches the transport and never reaches the inner backend.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from zgw_provider_openai_compatible.adapter import OpenAiCompatibleBackend

from zugzwang_chess.cognition import ChessPerception
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_core.ports.model import CallContext, Capability, ModelRef, ModelRequest
from zugzwang_runtime.artifacts.cas import ContentAddressedStore
from zugzwang_runtime.cognition.loop import CognitiveLoop
from zugzwang_runtime.cognition.session import DecisionSession
from zugzwang_runtime.execution.backend_caller import RecordingBackend
from zugzwang_runtime.persistence.cognition import CognitionJournal
from zugzwang_runtime.persistence.database import Database
from zugzwang_runtime.persistence.repositories import SchemaManager

pytestmark = pytest.mark.contract

POLICY_HASH = "b" * 64


def _provider_handler(
    seen: list[dict[str, Any]], responses_profile: bool, root_node: str = "node-root"
):
    """Canned provider: round 1 → observe tool call; with a tool result in the
    request → finalize tool call. Provider-style ids are intentional."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen.append({"path": request.url.path, "body": body})
        has_tool_result = any(
            (
                part.get("type") == "function_call_output"
                if responses_profile
                else part.get("role") == "tool"
            )
            for part in body.get("input", body.get("messages", []))
            if isinstance(part, dict)
        )
        call_id, tool, args = (
            ("call_7", "board_observe", {"node_id": root_node})
            if not has_tool_result
            else ("call_8", "board_finalize", {"node_id": root_node, "action": "e2e4"})
        )
        if responses_profile:
            return httpx.Response(
                200,
                json={
                    "id": "resp_1",
                    "object": "response",
                    "status": "completed",
                    "model": "m",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": call_id,
                            "name": tool,
                            "arguments": json.dumps(args),
                        }
                    ],
                    "usage": {
                        "input_tokens": 11,
                        "output_tokens": 5,
                        "total_tokens": 16,
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": call_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool,
                                        "arguments": json.dumps(args),
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16},
            },
        )

    return handler


@pytest.fixture()
def harness(tmp_path):
    database = Database(tmp_path / "state.db", wal_policy="ephemeral")
    engine = database.open()
    SchemaManager(engine).upgrade()
    with engine.connect() as conn:
        for stmt in (
            "INSERT INTO artifacts (artifact_id, algorithm, size_bytes, media_type, "
            "relative_path, created_at) VALUES ('art:seed','sha256',1,"
            "'application/json','cb/seed.json','2026-09-06T00:00:00Z')",
            "INSERT INTO runs (run_id, condition_id, status, protocol_hash, "
            "declared_assistance, projection_version, assistance_violated) "
            "VALUES ('run-1','cond-1','RUNNING','proto','H0',0,0)",
            "INSERT INTO episodes (episode_id, run_id, ordinal, task_type, seed, "
            "status, assistance_violated) VALUES ('ep-1','run-1',0,"
            "'chess.full_game',7,'RUNNING',0)",
            "INSERT INTO steps (step_id, episode_id, ordinal, actor_id, status, "
            "assistance_violated) VALUES ('st-1','ep-1',0,'model:main','RUNNING',0)",
            "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
            "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
            "status, created_at) VALUES ('sess-1','run-1','alg','0.1','ns',"
            "'node-root','{}','{}','RUNNING','2026-09-06T00:00:00Z')",
            "INSERT INTO search_nodes (node_id, search_session_id, position_key, "
            "trajectory_key, state_ref, depth, terminal, created_by, status) "
            "VALUES ('node-root','sess-1','pos:root','traj:root','cas://root',"
            "0,0,'perception','OPEN')",
            "INSERT INTO search_sessions (search_session_id, run_id, algorithm, "
            "algorithm_version, namespace, root_node_id, budgets_json, stats_json, "
            "status, created_at) VALUES ('sess-2','run-1','alg','0.1','ns',"
            "'node-root-2','{}','{}','RUNNING','2026-09-06T00:00:00Z')",
            "INSERT INTO search_nodes (node_id, search_session_id, position_key, "
            "trajectory_key, state_ref, depth, terminal, created_by, status) "
            "VALUES ('node-root-2','sess-2','pos:root','traj:root','cas://root',"
            "0,0,'perception','OPEN')",
        ):
            conn.execute(text(stmt))
        conn.commit()
    return database, engine, ContentAddressedStore(tmp_path / "cas")


def _session(harness, decision_id, ordinal: int = 0, search_session_id: str = "sess-1"):
    database, engine, cas = harness
    root_node = "node-root-2" if search_session_id == "sess-2" else "node-root"
    return DecisionSession.open(
        decision_id=decision_id,
        step_id="st-1",
        decision_ordinal=ordinal,
        search_session_id=search_session_id,
        strategy_id="chess.cognitive_navigation",
        strategy_version="0.2.0",
        interaction_mode="native_tools",
        policy_hash=POLICY_HASH,
        config={},
        states={root_node: ChessGameState()},
        journal=CognitionJournal(database),
        perception=ChessPerception(
            environment=StandardChessEnvironment(),
            rules_version="standard/v1",
            policy_hash=POLICY_HASH,
        ),
        cas=cas,
        engine=engine,
    )


def _run_loop(
    harness,
    decision_id,
    profile: str,
    seen: list[dict[str, Any]],
    ordinal: int = 0,
    search_session_id: str = "sess-1",
):
    session = _session(harness, decision_id, ordinal, search_session_id)
    backend = OpenAiCompatibleBackend(
        base_url="http://mock.local",
        api_key="test-key-offline",
        transport=httpx.MockTransport(
            _provider_handler(
                seen, profile == "responses", root_node=session.root_node_id or "node-root"
            )
        ),
        profile="openai-responses" if profile == "responses" else "openai-chat-completions",
    )
    loop = CognitiveLoop(
        decision_id=session.decision_id,
        journal=session.journal,
        broker_factory=session.new_broker_for_round,
        backend=backend,
        context_artifact_id=session.round_context_artifact_id,
        model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
        max_rounds=4,
    )
    return session, asyncio.run(loop.run())


def test_provider_ids_survive_full_composition(harness) -> None:
    """TEST-026 via the productive path: 'call_7'/'call_8' reach the journal."""
    seen: list[dict[str, Any]] = []
    session, result = _run_loop(harness, "dec-comp-0001", "chat", seen)
    assert result.status == "COMMITTED", result.trace_record
    assert result.selected_action == "e2e4"
    assert [entry["path"] for entry in seen] == ["/chat/completions"] * 2
    with harness[1].connect() as conn:
        rows = conn.execute(
            text(
                "SELECT provider_tool_call_id, tool_name, status FROM cb_tool_operations "
                "WHERE decision_id = :id ORDER BY created_at"
            ),
            {"id": session.decision_id},
        ).fetchall()
    provider_ids = [row[0] for row in rows]
    assert "call_7" in provider_ids, provider_ids
    assert all(row[2] == "COMMITTED" for row in rows)
    # board_finalize never becomes a tool operation (the loop validates it
    # against the root itself); its provider id lives in the call record.
    assert result.calls[-1].tool_call_ids == ("call_8",)
    assert result.calls[0].tool_call_ids[0] == "call_7"


def test_route_profiles_same_effect_distinct_wire(harness) -> None:
    """TEST-027/TEST-064 groundwork: both routes produce the same committed
    decision through the productive loop, over genuinely different endpoints."""
    chat_seen: list[dict[str, Any]] = []
    responses_seen: list[dict[str, Any]] = []
    _session_c, chat_result = _run_loop(harness, "dec-comp-0002", "chat", chat_seen)
    _session_r, responses_result = _run_loop(
        harness,
        "dec-comp-0003",
        "responses",
        responses_seen,
        ordinal=1,
        search_session_id="sess-2",
    )
    assert chat_result.status == "COMMITTED" and responses_result.status == "COMMITTED", (
        chat_result.trace_record,
        responses_result.trace_record,
    )
    assert chat_result.selected_action == responses_result.selected_action == "e2e4"
    assert {entry["path"] for entry in chat_seen} == {"/chat/completions"}
    assert {entry["path"] for entry in responses_seen} == {"/responses"}


def test_recording_backend_capability_gate_refuses_before_wire() -> None:
    """The gate runs in infer(): an unsupported request never reaches the
    transport nor the inner backend (TEST-065 direction)."""
    from zugzwang_runtime.fakes.fake_cognitive_backend import FakeCognitiveBackend

    inner = FakeCognitiveBackend(
        [lambda messages: {"tool": "board_observe", "arguments": {"node_id": "n"}}]
    )
    recording = RecordingBackend(inner=inner, writer=None, event_sink=None)  # type: ignore[arg-type]
    request = ModelRequest(
        model=ModelRef(backend="provider.openai_compatible", provider="mock", model="m"),
        messages=(),
        required_capabilities=frozenset({Capability.MULTIMODAL_IMAGE}),
    )
    from zugzwang_core.domain.errors import CapabilityMissingError

    with pytest.raises(CapabilityMissingError):
        asyncio.run(recording.infer(request, CallContext(run_id="run-1")))
    assert inner.calls == 0, "refused request never reached the inner backend"
