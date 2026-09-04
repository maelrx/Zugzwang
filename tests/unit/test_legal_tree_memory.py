"""Contract tests for the explicit R7 legal-tree and memory ablation."""

from __future__ import annotations

import json

import pytest


class _LegalTreeBackend:
    def __init__(self) -> None:
        self.requests = []
        self._outputs = (
            json.dumps(
                {
                    "critical_map": "the king is safe; inspect checks and captures",
                    "hanging_pieces": [],
                    "tactical_ideas": ["occupy the center"],
                    "candidate_moves": ["e2e4", "e2e5"],
                    "illegal_probes": ["e2e5"],
                    "confidence": 0.8,
                }
            ),
            json.dumps(
                {
                    "variants": [
                        {
                            "root_move": "e2e4",
                            "reply_move": "e7e5",
                            "assessment": "both sides contest the center",
                            "risks": ["do not lose king safety"],
                        }
                    ],
                    "candidate_moves": ["e2e4"],
                }
            ),
            json.dumps(
                {
                    "move": "e2e4",
                    "review": "the legal branch keeps the center and king safe",
                    "critical_risks_addressed": ["king safety"],
                    "confidence": 0.9,
                }
            ),
        )

    async def infer(self, request, context):
        from zugzwang_core.domain.money import TokenUsage, UsageSource
        from zugzwang_core.ports.model import (
            NormalizedResponse,
            ProviderResult,
            StopReason,
            TextPart,
        )

        self.requests.append((request, context))
        output = self._outputs[len(self.requests) - 1]
        return ProviderResult(
            response=NormalizedResponse(
                content_parts=(TextPart(text=output),),
                stop_reason=StopReason(canonical="end_turn"),
                model_requested=request.model,
                model_reported=request.model.model,
                usage=TokenUsage(
                    input_tokens=10,
                    output_tokens=20,
                    source=UsageSource.ESTIMATED,
                ),
                adapter_version="test",
            )
        )


def _context(*, backend, gateway, workspace, memory, mode: str = "episodic"):
    from zugzwang_core.ports.model import ModelRef
    from zugzwang_core.ports.rules import DecisionCapabilities
    from zugzwang_core.ports.strategy import DecisionContext

    return DecisionContext(
        run_id="run_test",
        episode_id="ep_test",
        step_id="stp_test",
        model=ModelRef(backend="fake.backend", provider="fake", model="scripted"),
        backend=backend,
        tools={},
        seed=7,
        config={
            "search": {
                "memory_mode": mode,
                "max_root_branches": 2,
                "max_depth_plies": 2,
            }
        },
        capabilities=DecisionCapabilities(
            validate_action=True,
            enumerate_actions=True,
            transition_sandbox=True,
            query_terminal=True,
            validation_feedback="enumerated",
        ),
        legality_gateway=gateway,
        search_workspace=workspace,
        search_memory=memory,
    )


@pytest.mark.asyncio
async def test_r7_exposes_legal_set_to_each_role_and_records_illegal_probe() -> None:
    from zugzwang_chess.environment.standard import ChessGameState, StandardChessRulesKernel
    from zugzwang_chess.strategies.legal_tree_memory import LegalTreeMemoryStrategy
    from zugzwang_core.ports.rules import DecisionCapabilities, LegalityGatewayConfig
    from zugzwang_runtime.execution.legality import LegalityGateway
    from zugzwang_runtime.search import SearchMemoryFabric, SearchWorkspace

    state = ChessGameState()
    kernel = StandardChessRulesKernel()
    workspace = SearchWorkspace(kernel=kernel, root_state=state, max_nodes=16, max_depth_plies=2)
    memory = SearchMemoryFabric(workspace)
    gateway = LegalityGateway(
        kernel=kernel,
        config=LegalityGatewayConfig(enumerate={"enabled": True}),
    ).bind(
        state=state,
        capabilities=DecisionCapabilities(
            validate_action=True,
            enumerate_actions=True,
            transition_sandbox=True,
            query_terminal=True,
            validation_feedback="enumerated",
        ),
    )
    backend = _LegalTreeBackend()

    trace = await LegalTreeMemoryStrategy().decide(
        {
            "fen": state.fen,
            "side_to_move": "white",
            "move_number": 1,
            "history": [],
        },
        _context(
            backend=backend,
            gateway=gateway,
            workspace=workspace,
            memory=memory,
        ),
    )

    assert trace.declared_regime == "R7"
    assert trace.final_action == "e2e4"
    assert len(trace.calls) == 3
    assert gateway.stats.enumeration_queries >= 2
    assert all(
        "LEGAL ROOT MOVES" in request.messages[0].parts[0].text
        and "e2e4" in request.messages[0].parts[0].text
        for request, _ in backend.requests
    )
    assert any(not edge.legal and edge.proposed_action == "e2e5" for edge in workspace.edges)
    assert any(edge.legal and edge.proposed_action == "e2e4" for edge in workspace.edges)
    assert memory.items
    rationale = trace.selection_rationale
    assert rationale is not None
    assert rationale["legal_action_set"]["count"] > 0
    assert rationale["memory_mode"] == "episodic"
    assert "e2e5" in rationale["illegal_probes"]
    assert rationale["variant_branches"]
    assert rationale["root_branches"][0]["legal_reply_moves"]


@pytest.mark.unit
def test_persistent_memory_reseeds_a_new_turn_but_episodic_memory_does_not() -> None:
    from zugzwang_chess.environment.standard import ChessGameState, StandardChessRulesKernel
    from zugzwang_runtime.search import RetrievalBudget, SearchMemoryFabric, SearchWorkspace

    kernel = StandardChessRulesKernel()
    first = SearchWorkspace(kernel=kernel, root_state=ChessGameState(), max_nodes=8)
    first_memory = SearchMemoryFabric(first)
    first_memory.record(
        node_id=first.root_id,
        kind="failure",
        content="avoid the central tactical failure",
        generated_by="model",
    )

    second = SearchWorkspace(kernel=kernel, root_state=ChessGameState(), max_nodes=8)
    persistent = SearchMemoryFabric(second, initial_items=first_memory.items)
    episodic = SearchMemoryFabric(second)

    assert persistent.retrieve("exact_state", second.root_id, RetrievalBudget(max_items=4)).items
    assert not episodic.retrieve("exact_state", second.root_id, RetrievalBudget(max_items=4)).items
