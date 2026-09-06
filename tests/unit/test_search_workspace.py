"""Pure-search invariants: immutable branches, formal tools and provenance."""

from __future__ import annotations

import pytest


def _workspace(*, max_nodes: int = 16):
    from zugzwang_chess.environment.standard import ChessGameState, StandardChessRulesKernel
    from zugzwang_runtime.search import SearchWorkspace

    return SearchWorkspace(
        kernel=StandardChessRulesKernel(),
        root_state=ChessGameState(),
        max_nodes=max_nodes,
        max_depth_plies=4,
    )


@pytest.mark.unit
def test_search_try_move_does_not_mutate_root_and_binary_validation_has_no_list() -> None:
    workspace = _workspace()
    root_before = workspace.state(workspace.root_id).fingerprint()

    validation = workspace.validate_move(workspace.root_id, "e2e4")
    assert validation == {"legal": True}
    result = workspace.try_move(workspace.root_id, "e2e4", created_by="candidate-generator")

    assert result["legal"] is True
    assert result["child_state_ref"]
    assert workspace.state(workspace.root_id).fingerprint() == root_before
    assert workspace.state(result["child_node_id"]).move_stack == ("e2e4",)


@pytest.mark.unit
def test_illegal_edge_is_logged_without_child_state() -> None:
    workspace = _workspace()
    result = workspace.try_move(workspace.root_id, "e2e5", created_by="candidate-generator")

    assert result == {
        "legal": False,
        "reason": "ILLEGAL_PIECE_MOVEMENT",
        "child_node_id": None,
        "child_state_ref": None,
        "terminal": False,
    }
    assert workspace.edges[-1].legal is False
    assert workspace.edges[-1].child_node_id is None


@pytest.mark.unit
def test_transposition_index_preserves_trajectory_identity() -> None:
    workspace = _workspace()
    node = workspace.root_id
    for move in ("g1f3", "g8f6", "f3g1", "f6g8"):
        node = workspace.try_move(node, move, created_by="model")["child_node_id"]

    assert node is not None
    assert workspace.nodes[node].position_key == workspace.nodes[workspace.root_id].position_key
    assert workspace.nodes[node].trajectory_key != workspace.nodes[workspace.root_id].trajectory_key
    assert workspace.stats["transpositions"] >= 1


@pytest.mark.unit
def test_search_node_and_edge_ids_are_scoped_to_their_session() -> None:
    from zugzwang_chess.environment.standard import ChessGameState, StandardChessRulesKernel
    from zugzwang_runtime.search import SearchWorkspace

    first = SearchWorkspace(
        kernel=StandardChessRulesKernel(),
        root_state=ChessGameState(),
        session_id="session_a",
    )
    second = SearchWorkspace(
        kernel=StandardChessRulesKernel(),
        root_state=ChessGameState(),
        session_id="session_b",
    )

    first_edge = first.try_move(first.root_id, "e2e4", created_by="model")
    second_edge = second.try_move(second.root_id, "e2e4", created_by="model")

    assert first.root_id != second.root_id
    assert first_edge["child_node_id"] != second_edge["child_node_id"]
    assert first.edges[0].edge_id != second.edges[0].edge_id


@pytest.mark.unit
def test_search_budget_and_evaluation_firewall() -> None:
    from zugzwang_core.domain.errors import BudgetExceededError, SecurityError

    workspace = _workspace(max_nodes=1)
    with pytest.raises(BudgetExceededError):
        workspace.try_move(workspace.root_id, "e2e4", created_by="model")
    with pytest.raises(SecurityError):
        workspace.record_analysis(workspace.root_id, "evaluation://eval/node/1")


@pytest.mark.unit
def test_memory_retrieval_retains_provenance_and_rejects_evaluation_namespace() -> None:
    from zugzwang_core.domain.errors import SecurityError
    from zugzwang_runtime.search import RetrievalBudget, SearchMemoryFabric

    workspace = _workspace()
    memory = SearchMemoryFabric(workspace)
    memory.record(
        node_id=workspace.root_id,
        kind="model_analysis",
        content="candidate e2e4",
        generated_by="muse-spark-1.3",
    )
    result = memory.retrieve("exact_state", workspace.root_id, RetrievalBudget(max_items=4))
    assert result.items[0].source_node_ids == (workspace.root_id,)
    assert result.items[0].generated_by == "muse-spark-1.3"
    with pytest.raises(SecurityError):
        memory.record(
            node_id=workspace.root_id,
            kind="engine",
            content="evaluation://eval/node/1",
            generated_by="stockfish",
        )


@pytest.mark.unit
def test_deterministic_memory_retrievers_and_budget() -> None:
    from zugzwang_runtime.search import RetrievalBudget, SearchMemoryFabric

    workspace = _workspace()
    child = workspace.try_move(workspace.root_id, "e2e4", created_by="model")["child_node_id"]
    sibling = workspace.try_move(workspace.root_id, "g1f3", created_by="model")["child_node_id"]
    memory = SearchMemoryFabric(workspace)
    memory.record(
        node_id=workspace.root_id,
        kind="ancestor_note",
        content="root context",
        generated_by="model",
    )
    memory.record(
        node_id=child,
        kind="failure",
        content="tactical failure",
        generated_by="model",
    )
    memory.record(
        node_id=sibling,
        kind="candidate",
        content="sibling candidate",
        generated_by="model",
    )

    assert memory.retrieve("ancestors", child, RetrievalBudget(max_items=1)).items
    assert memory.retrieve("siblings", sibling, RetrievalBudget(max_items=1)).items
    assert (
        memory.retrieve("failure", child, RetrievalBudget(max_items=1), text="tactical")
        .items[0]
        .kind
        == "failure"
    )
    assert len(memory.retrieve("failure", child, RetrievalBudget(max_items=0)).items) == 0


@pytest.mark.asyncio
async def test_r6_batched_tree_commits_a_model_only_move() -> None:
    from zugzwang_chess.strategies.batched_tree import BatchedTreeStrategy
    from zugzwang_core.ports.model import ModelRef
    from zugzwang_core.ports.strategy import DecisionContext
    from zugzwang_runtime.fakes import DeterministicModelBackend, FakeBackendRule
    from zugzwang_runtime.search import SearchMemoryFabric

    workspace = _workspace(max_nodes=16)
    memory = SearchMemoryFabric(workspace)
    backend = DeterministicModelBackend(
        rules=(
            FakeBackendRule(
                when={"fingerprint_contains": "chess-r6-candidates"},
                output='{"candidates":[{"move":"e2e4"},{"move":"e2e5"}]}',
            ),
            FakeBackendRule(
                when={"fingerprint_contains": "chess-r6-judge"},
                output="1",
            ),
        )
    )
    from zugzwang_chess.environment.standard import StandardChessEnvironment

    strategy = BatchedTreeStrategy(initial_candidates=2, judges=3)
    context = DecisionContext(
        run_id="run_test",
        episode_id="ep_test",
        step_id="stp_test",
        model=ModelRef(backend="fake.backend", provider="fake", model="scripted"),
        backend=backend,
        tools={},
        seed=7,
        search_workspace=workspace,
        search_memory=memory,
    )
    observation = StandardChessEnvironment().observe(
        workspace.state(workspace.root_id),
        __import__(
            "zugzwang_core.ports.environment", fromlist=["ObservationPolicy"]
        ).ObservationPolicy(settings={"position": {"fen": True}, "side_to_move": True}),
    )

    trace = await strategy.decide(observation, context)

    assert trace.final_action == "e2e4"
    assert trace.declared_regime == "R6"
    assert trace.selection_rationale is not None
    assert workspace.stats["branch_nodes_created"] == 1
    assert memory.items
