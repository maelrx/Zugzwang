"""Contract tests for the one-agent full-capability tree strategy."""

from __future__ import annotations

import json

import pytest


class _SingleAgentBackend:
    def __init__(self) -> None:
        self.requests = []

    async def infer(self, request, context):
        from zugzwang_core.domain.money import TokenUsage, UsageSource
        from zugzwang_core.ports.model import (
            NormalizedResponse,
            ProviderResult,
            StopReason,
            TextPart,
        )

        self.requests.append((request, context))
        output = json.dumps(
            {
                "critical_map": "inspect checks, captures and king safety",
                "hanging_pieces": [],
                "tactical_ideas": ["occupy the center"],
                "candidate_moves": ["e2e4", "e2e5"],
                "illegal_probes": ["e2e5"],
                "variants": [
                    {
                        "root_move": "e2e4",
                        "reply_move": "e7e5",
                        "assessment": "contest the center",
                        "risks": ["watch king safety"],
                    }
                ],
                "move": "e2e4",
                "analysis": "e2e4 is the reviewed legal root move",
                "confidence": 0.9,
            }
        )
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


@pytest.mark.asyncio
async def test_single_agent_sees_legal_tree_and_records_one_decision_call() -> None:
    from zugzwang_chess.environment.standard import ChessGameState, StandardChessRulesKernel
    from zugzwang_chess.strategies.single_agent_tree import SingleAgentTreeStrategy
    from zugzwang_core.ports.model import ModelRef
    from zugzwang_core.ports.rules import DecisionCapabilities, LegalityGatewayConfig
    from zugzwang_core.ports.strategy import DecisionContext
    from zugzwang_runtime.execution.legality import LegalityGateway
    from zugzwang_runtime.search import SearchMemoryFabric, SearchWorkspace

    state = ChessGameState()
    kernel = StandardChessRulesKernel()
    workspace = SearchWorkspace(kernel=kernel, root_state=state, max_nodes=64, max_depth_plies=2)
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
    backend = _SingleAgentBackend()
    context = DecisionContext(
        run_id="run_test",
        episode_id="ep_test",
        step_id="stp_test",
        model=ModelRef(backend="fake.backend", provider="fake", model="scripted"),
        backend=backend,
        tools={},
        seed=7,
        config={
            "search": {
                "memory_mode": "episodic",
                "reply_scope": "all",
                "max_root_branches": 4,
                "max_affordance_roots": 32,
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

    trace = await SingleAgentTreeStrategy().decide(
        {
            "fen": state.fen,
            "side_to_move": "white",
            "move_number": 1,
            "history": [],
        },
        context,
    )

    assert trace.declared_regime == "R7"
    assert trace.final_action == "e2e4"
    assert len(trace.calls) == 1
    assert trace.assistance_impacts[0].h.name == "H4"
    assert gateway.stats.enumeration_queries >= 2
    assert any(not edge.legal and edge.proposed_action == "e2e5" for edge in workspace.edges)
    rationale = trace.selection_rationale
    assert rationale is not None
    assert rationale["legal_action_set"]["count"] == 20
    assert len(rationale["root_branches"]) == 20
    assert rationale["root_branches"][0]["legal_reply_moves"]
    assert rationale["variant_branches"][0]["legal"]
    prompt = backend.requests[0][0].messages[0].parts[0].text
    assert "LEGAL ROOT MOVES" in prompt
    assert "LEGAL REPLIES AFTER e2e4" in prompt
