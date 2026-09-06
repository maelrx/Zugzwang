"""Projection of an in-memory SearchWorkspace into SQLite + CAS."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from zugzwang_core.domain.clocks import to_iso_z, utc_now
from zugzwang_core.domain.events import EventContext, EventEnvelope
from zugzwang_core.domain.ids import new_id

from ..artifacts.cas import ContentAddressedStore
from ..execution.evidence import store_json_artifact
from ..persistence.writer import (
    InsertSearchEdgeCommand,
    InsertSearchNodeCommand,
    InsertSearchRetrievalEventCommand,
    InsertSearchSessionCommand,
    UpdateSearchSessionCommand,
)
from .memory import SearchMemoryFabric
from .workspace import SearchWorkspace


def persist_workspace(
    *,
    workspace: SearchWorkspace,
    writer: Any,
    cas: ContentAddressedStore,
    run_id: str,
    episode_id: str,
    step_id: str,
    algorithm: str = "R6-BatchedTree",
    algorithm_version: str = "0.1.0",
    memory: SearchMemoryFabric | None = None,
    status: str = "COMPLETED",
    event_sink: Any = None,
) -> str:
    """Persist graph projections and return its immutable CAS artifact id."""
    now = to_iso_z(utc_now())
    writer.enqueue(
        InsertSearchSessionCommand(
            row={
                "search_session_id": workspace.session_id,
                "run_id": run_id,
                "episode_id": episode_id,
                "step_id": step_id,
                "algorithm": algorithm,
                "algorithm_version": algorithm_version,
                "namespace": "search://",
                "root_node_id": workspace.root_id,
                "budgets_json": {
                    "max_nodes": workspace.max_nodes,
                    "max_depth_plies": workspace.max_depth_plies,
                    "max_validation_queries": workspace.max_validation_queries,
                    "max_transition_queries": workspace.max_transition_queries,
                },
                "stats_json": workspace.stats,
                "status": status,
                "created_at": now,
                "finished_at": now,
            }
        )
    )
    for node in workspace.nodes.values():
        writer.enqueue(
            InsertSearchNodeCommand(
                row={
                    "node_id": node.node_id,
                    "search_session_id": workspace.session_id,
                    "parent_id": node.parent_id,
                    "position_key": node.position_key,
                    "trajectory_key": node.trajectory_key,
                    "state_ref": node.state_ref,
                    "action_from_parent": node.action_from_parent,
                    "root_action": node.root_action,
                    "depth": node.depth,
                    "side_to_move": node.side_to_move,
                    "terminal": 1 if node.terminal else 0,
                    "created_by": node.created_by,
                    "analysis_ref": node.analysis_ref,
                    "status": node.status,
                }
            )
        )
    for edge in workspace.edges:
        writer.enqueue(
            InsertSearchEdgeCommand(
                row={
                    "edge_id": edge.edge_id,
                    "search_session_id": workspace.session_id,
                    "parent_node_id": edge.parent_node_id,
                    "child_node_id": edge.child_node_id,
                    "proposed_action": edge.proposed_action,
                    "legal": 1 if edge.legal else 0,
                    "rejection_reason": edge.rejection_reason,
                    "created_by": edge.created_by,
                }
            )
        )
    for event in workspace.events:
        if event_sink is not None:
            event_sink.append(
                EventEnvelope.create(
                    event_type=event["event_type"],
                    payload=event.get("payload", {}),
                    stream_type="step",
                    stream_id=step_id,
                    sequence=0,
                    context=EventContext(
                        run_id=run_id,
                        episode_id=episode_id,
                        step_id=step_id,
                    ),
                )
            )
        if event["event_type"] != "search.node.retrieved":
            continue
        payload = event.get("payload", {})
        writer.enqueue(
            InsertSearchRetrievalEventCommand(
                row={
                    "retrieval_event_id": str(new_id("evt")),
                    "search_session_id": workspace.session_id,
                    "node_id": str(payload.get("node_id", workspace.root_id)),
                    "retriever": str(payload.get("retriever", "unknown")),
                    "budget_json": payload.get("budget", {}),
                    "result_refs_json": payload.get("result_memory_ids", []),
                    "created_at": now,
                }
            )
        )
    graph_ref = store_json_artifact(
        cas=cas,
        writer=writer,
        payload={
            **workspace.to_artifact(),
            "memory": [asdict(item) for item in memory.items] if memory is not None else [],
        },
        media_type="application/vnd.zugzwang.search-graph+json",
        redaction_policy="standard",
    ).as_id()
    writer.enqueue(
        UpdateSearchSessionCommand(
            search_session_id=workspace.session_id,
            values={"stats_json": workspace.stats, "status": status, "finished_at": now},
        )
    )
    return graph_ref
