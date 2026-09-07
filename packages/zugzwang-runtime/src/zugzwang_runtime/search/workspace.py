"""Immutable, model-only hypothetical search workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zugzwang_core.domain.canonical import hash_canonical
from zugzwang_core.domain.errors import BudgetExceededError, SecurityError
from zugzwang_core.ports.rules import LegalityResult, RulesKernel


@dataclass(frozen=True, slots=True)
class SearchNode:
    node_id: str
    parent_id: str | None
    position_key: str
    trajectory_key: str
    state_ref: str
    action_from_parent: str | None
    root_action: str | None
    depth: int
    side_to_move: str | None
    terminal: bool
    created_by: str
    analysis_ref: str | None = None
    status: str = "frontier"


@dataclass(frozen=True, slots=True)
class SearchEdge:
    edge_id: str
    parent_node_id: str
    child_node_id: str | None
    proposed_action: str
    legal: bool
    rejection_reason: str | None = None
    created_by: str = "model"


class SearchWorkspace:
    """A bounded DAG of model-generated branches over a trusted rules kernel.

    The canonical game state is never passed back to the caller as a mutable
    work buffer.  Each committed hypothetical state is the result returned by
    ``RulesKernel.transition`` and is addressed by a fingerprint.
    """

    def __init__(
        self,
        *,
        kernel: RulesKernel,
        root_state: Any,
        max_nodes: int = 64,
        max_depth_plies: int = 6,
        max_validation_queries: int = 128,
        max_transition_queries: int = 64,
        session_id: str | None = None,
    ) -> None:
        self.kernel = kernel
        self.max_nodes = max_nodes
        self.max_depth_plies = max_depth_plies
        self.max_validation_queries = max_validation_queries
        self.max_transition_queries = max_transition_queries
        self.session_id = session_id or "search_local"
        self.nodes: dict[str, SearchNode] = {}
        self.edges: list[SearchEdge] = []
        self._states: dict[str, Any] = {}
        self._trajectory_index: dict[str, str] = {}
        self._position_index: dict[str, list[str]] = {}
        self._analyses: dict[str, list[str]] = {}
        self._events: list[dict[str, Any]] = []
        self._validation_queries = 0
        self._transition_queries = 0
        self._duplicate_states = 0
        self._transpositions = 0
        self._root_state = root_state
        root_position = _position_key(root_state)
        root_trajectory = hash_canonical(
            {"parent": None, "action": None, "state": _state_fingerprint(root_state)}
        )
        self.root_id = self._node_id(root_trajectory)
        root = SearchNode(
            node_id=self.root_id,
            parent_id=None,
            position_key=root_position,
            trajectory_key=root_trajectory,
            state_ref=_state_ref(root_state),
            action_from_parent=None,
            root_action=None,
            depth=0,
            side_to_move=_side_to_move(root_state),
            terminal=bool(self.kernel.terminal(root_state)),
            created_by="root",
            status="terminal" if bool(self.kernel.terminal(root_state)) else "frontier",
        )
        self.nodes[root.node_id] = root
        self._states[root.node_id] = root_state
        self._trajectory_index[root.trajectory_key] = root.node_id
        self._position_index.setdefault(root.position_key, []).append(root.node_id)
        self._event("search.session.started", {"root_node_id": self.root_id})

    def register_anchor(
        self,
        *,
        node_id: str,
        state: Any,
        depth: int = 0,
        created_by: str = "anchor",
    ) -> str:
        """Register an externally-addressed integral state as an expansion root.

        Decision sessions bind nodes under caller-chosen ids; the workspace
        normally mints content-addressed ids from the trajectory. Anchoring
        lets ``try_move`` operate on the caller's node id directly so both
        graphs stay in one identity namespace (§9.1: one graph per decision).
        The anchor is a root-like node: no parent, caller-supplied depth.
        """
        if node_id in self.nodes:
            raise ValueError(f"anchor {node_id!r} already exists in the workspace")
        position_key = _position_key(state)
        trajectory_key = hash_canonical(
            {"parent": None, "action": None, "state": _state_fingerprint(state)}
        )
        terminal = bool(self.kernel.terminal(state))
        node = SearchNode(
            node_id=node_id,
            parent_id=None,
            position_key=position_key,
            trajectory_key=trajectory_key,
            state_ref=_state_ref(state),
            action_from_parent=None,
            root_action=None,
            depth=depth,
            side_to_move=_side_to_move(state),
            terminal=terminal,
            created_by=created_by,
            status="terminal" if terminal else "frontier",
        )
        self.nodes[node.node_id] = node
        self._states[node.node_id] = state
        self._trajectory_index.setdefault(trajectory_key, node.node_id)
        self._position_index.setdefault(position_key, []).append(node.node_id)
        self._event("search.node.anchored", {"node_id": node.node_id})
        return node.node_id

    @property
    def stats(self) -> dict[str, int]:
        return {
            "validation_queries": self._validation_queries,
            "transition_queries": self._transition_queries,
            "branch_nodes_created": len(self.nodes) - 1,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "duplicate_states": self._duplicate_states,
            "transpositions": self._transpositions,
            "max_depth": max((node.depth for node in self.nodes.values()), default=0),
        }

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._events)

    def record_retrieval_event(
        self,
        retriever: str,
        node_id: str,
        count: int,
        *,
        result_memory_ids: tuple[str, ...] = (),
        budget: int = 0,
    ) -> None:
        self._node(node_id)
        self._event(
            "search.node.retrieved",
            {
                "node_id": node_id,
                "retriever": retriever,
                "count": count,
                "result_memory_ids": list(result_memory_ids),
                "budget": {"max_items": budget},
            },
        )

    def state(self, node_id: str) -> Any:
        if node_id not in self._states:
            raise KeyError(node_id)
        return self._states[node_id]

    def validate_move(self, node_id: str, action: Any) -> dict[str, bool]:
        """Pure binary validation; never returns the legal action set."""
        result = self._validate(node_id, action)
        return {"legal": bool(result.legal)}

    def try_move(self, node_id: str, action: Any, *, created_by: str) -> dict[str, Any]:
        parent = self._node(node_id)
        if parent.depth >= self.max_depth_plies:
            raise BudgetExceededError(
                "search depth budget exhausted",
                technical_context=f"depth={parent.depth} limit={self.max_depth_plies}",
            )
        self._require_model_agent(created_by)
        result = self._validate(node_id, action)
        proposed = str(action)
        if not result.legal:
            edge = SearchEdge(
                edge_id=self._edge_id(parent, proposed),
                parent_node_id=node_id,
                child_node_id=None,
                proposed_action=proposed,
                legal=False,
                rejection_reason=result.reason,
                created_by=created_by,
            )
            self.edges.append(edge)
            self._event(
                "search.edge.rejected",
                {"edge_id": edge.edge_id, "node_id": node_id, "action": proposed},
            )
            return {
                "legal": False,
                "reason": result.reason,
                "child_node_id": None,
                "child_state_ref": None,
                "terminal": False,
            }
        self._ensure_transition_budget()
        self._transition_queries += 1
        transition = self.kernel.transition(self.state(node_id), result.action or action)
        child_state = transition.state
        trajectory_key = hash_canonical(
            {
                "parent": parent.trajectory_key,
                "action": proposed,
                "state": _state_fingerprint(child_state),
            }
        )
        existing = self._trajectory_index.get(trajectory_key)
        if existing is not None:
            child_id = existing
            self._duplicate_states += 1
        else:
            position_key = _position_key(child_state)
            if position_key in self._position_index:
                self._transpositions += 1
                self._event(
                    "search.transposition.found",
                    {"position_key": position_key, "parent_node_id": node_id},
                )
            child_id = self._create_node(
                parent=parent,
                child_state=child_state,
                proposed=proposed,
                trajectory_key=trajectory_key,
                created_by=created_by,
                terminal=bool(transition.terminal),
            )
        edge = SearchEdge(
            edge_id=self._edge_id(parent, proposed),
            parent_node_id=node_id,
            child_node_id=child_id,
            proposed_action=proposed,
            legal=True,
            created_by=created_by,
        )
        self.edges.append(edge)
        self._event(
            "search.edge.committed",
            {"edge_id": edge.edge_id, "parent_node_id": node_id, "child_node_id": child_id},
        )
        return {
            "legal": True,
            "child_node_id": child_id,
            "child_state_ref": self.nodes[child_id].state_ref,
            "terminal": bool(transition.terminal),
        }

    def batch_validate(
        self, node_id: str, actions: list[Any] | tuple[Any, ...]
    ) -> list[dict[str, bool]]:
        return [self.validate_move(node_id, action) for action in actions]

    def validate_line(self, node_id: str, actions: list[Any] | tuple[Any, ...]) -> dict[str, Any]:
        if len(actions) > self.max_depth_plies:
            raise BudgetExceededError(
                "search line exceeds depth budget",
                technical_context=f"depth={len(actions)} limit={self.max_depth_plies}",
            )
        current = node_id
        steps: list[dict[str, Any]] = []
        for action in actions:
            result = self.try_move(current, action, created_by="model-line")
            steps.append({"action": str(action), **result})
            if not result["legal"] or result["child_node_id"] is None:
                break
            current = str(result["child_node_id"])
            if result["terminal"]:
                break
        return {"legal": all(bool(step["legal"]) for step in steps), "steps": steps}

    def record_analysis(
        self, node_id: str, artifact_ref: str, *, generated_by: str = "model"
    ) -> None:
        self._node(node_id)
        lowered = f"{artifact_ref} {generated_by}".lower()
        if (
            artifact_ref.startswith("evaluation://")
            or "stockfish" in lowered
            or "engine" in lowered
        ):
            raise SecurityError("post-hoc evaluation artifacts are outside pure search namespace")
        self._analyses.setdefault(node_id, []).append(artifact_ref)
        self._event(
            "search.node.analyzed",
            {"node_id": node_id, "artifact_ref": artifact_ref, "generated_by": generated_by},
        )

    def to_artifact(self) -> dict[str, Any]:
        return {
            "schema_version": "zgw.search-graph/v1",
            "namespace": "search://",
            "search_session_id": self.session_id,
            "root_id": self.root_id,
            "stats": self.stats,
            "nodes": [
                {
                    **_node_payload(node),
                    "analysis_refs": self._analyses.get(node.node_id, []),
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "edge_id": edge.edge_id,
                    "parent_node_id": edge.parent_node_id,
                    "child_node_id": edge.child_node_id,
                    "proposed_action": edge.proposed_action,
                    "legal": edge.legal,
                    "rejection_reason": edge.rejection_reason,
                    "created_by": edge.created_by,
                }
                for edge in self.edges
            ],
            "events": list(self._events),
        }

    def _validate(self, node_id: str, action: Any) -> LegalityResult:
        self._node(node_id)
        self._ensure_validation_budget()
        self._validation_queries += 1
        canonical_action = action
        if isinstance(action, str):
            parsed = self.kernel.parse_action(action, "canonical")
            if not parsed.valid or parsed.parsed is None:
                result = LegalityResult(
                    legal=False,
                    action=action,
                    reason="ILLEGAL_PARSE",
                )
            else:
                canonical_action = parsed.parsed
                result = self.kernel.is_legal(self.state(node_id), canonical_action)
        else:
            result = self.kernel.is_legal(self.state(node_id), canonical_action)
        self._event(
            "search.edge.proposed",
            {"node_id": node_id, "action": str(action), "legal": bool(result.legal)},
        )
        return result

    def _create_node(
        self,
        *,
        parent: SearchNode,
        child_state: Any,
        proposed: str,
        trajectory_key: str,
        created_by: str,
        terminal: bool,
    ) -> str:
        if len(self.nodes) >= self.max_nodes:
            raise BudgetExceededError(
                "search node budget exhausted",
                technical_context=f"nodes={len(self.nodes)} limit={self.max_nodes}",
            )
        position_key = _position_key(child_state)
        child_id = self._node_id(trajectory_key)
        root_action = proposed if parent.parent_id is None else parent.root_action
        node = SearchNode(
            node_id=child_id,
            parent_id=parent.node_id,
            position_key=position_key,
            trajectory_key=trajectory_key,
            state_ref=_state_ref(child_state),
            action_from_parent=proposed,
            root_action=root_action,
            depth=parent.depth + 1,
            side_to_move=_side_to_move(child_state),
            terminal=terminal,
            created_by=created_by,
            status="terminal" if terminal else "frontier",
        )
        self.nodes[child_id] = node
        self._states[child_id] = child_state
        self._trajectory_index[trajectory_key] = child_id
        self._position_index.setdefault(position_key, []).append(child_id)
        self._event("search.node.created", {"node_id": child_id, "parent_id": parent.node_id})
        return child_id

    def _node(self, node_id: str) -> SearchNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"search node {node_id!r} not found") from exc

    def _ensure_validation_budget(self) -> None:
        if self._validation_queries >= self.max_validation_queries:
            raise BudgetExceededError("search validation budget exhausted")

    def _ensure_transition_budget(self) -> None:
        if self._transition_queries >= self.max_transition_queries:
            raise BudgetExceededError("search transition budget exhausted")

    def _node_id(self, trajectory_key: str) -> str:
        return f"node_{hash_canonical({'session': self.session_id, 'trajectory': trajectory_key})[:24]}"

    def _edge_id(self, parent: SearchNode, action: str) -> str:
        return f"edge_{hash_canonical({'session': self.session_id, 'parent': parent.node_id, 'action': action})[:24]}"

    @staticmethod
    def _require_model_agent(agent: str) -> None:
        lowered = agent.lower()
        if "stockfish" in lowered or "engine" in lowered or "tablebase" in lowered:
            raise SecurityError("engine-generated actions cannot enter pure search")

    def _event(self, event_type: str, payload: dict[str, Any]) -> None:
        self._events.append({"event_type": event_type, "payload": payload})


def _state_fingerprint(state: Any) -> str:
    value = getattr(state, "fingerprint", None)
    if callable(value):
        return str(value())
    if value is not None:
        return str(value)
    return hash_canonical(repr(state))


def _state_ref(state: Any) -> str:
    return f"search://state/{_state_fingerprint(state)}"


def _position_key(state: Any) -> str:
    fen = getattr(state, "fen", None)
    if isinstance(fen, str):
        parts = fen.split()
        return hash_canonical({"fen": " ".join(parts[:4])})
    return hash_canonical({"state": _state_fingerprint(state)})


def _side_to_move(state: Any) -> str | None:
    value = getattr(state, "side_to_move", None)
    if callable(value):
        value = value()
    return str(value) if value is not None else None


def _node_payload(node: SearchNode) -> dict[str, Any]:
    return {
        "node_id": node.node_id,
        "parent_id": node.parent_id,
        "position_key": node.position_key,
        "trajectory_key": node.trajectory_key,
        "state_ref": node.state_ref,
        "action_from_parent": node.action_from_parent,
        "root_action": node.root_action,
        "depth": node.depth,
        "side_to_move": node.side_to_move,
        "terminal": node.terminal,
        "created_by": node.created_by,
        "analysis_ref": node.analysis_ref,
        "status": node.status,
    }
