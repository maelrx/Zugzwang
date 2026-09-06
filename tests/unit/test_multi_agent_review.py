"""Contract tests for the explicit per-move R5 review chain."""

from __future__ import annotations

import json

import pytest


class _SpyBackend:
    def __init__(self) -> None:
        self.requests = []
        self._outputs = (
            json.dumps(
                {
                    "critical_map": "king safety and loose central pawn",
                    "hanging_pieces": [{"piece": "black queen", "square": "d8"}],
                    "tactical_ideas": ["develop with tempo"],
                    "candidate_moves": ["e2e4", "g1f3"],
                    "confidence": 0.7,
                }
            ),
            json.dumps(
                {
                    "plan": "occupy the center and develop",
                    "candidate_moves": ["e2e4", "g1f3"],
                    "preferred_move": "e2e4",
                    "risks": ["do not leave the king exposed"],
                }
            ),
            json.dumps(
                {
                    "move": "e2e4",
                    "review": "the move addresses the central tactic",
                    "critical_risks_addressed": ["development"],
                    "confidence": 0.8,
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


@pytest.mark.asyncio
async def test_multi_agent_review_records_ordered_roles_and_final_selection() -> None:
    from zugzwang_chess.strategies.multi_agent_review import MultiAgentReviewStrategy
    from zugzwang_core.ports.model import ModelRef
    from zugzwang_core.ports.strategy import DecisionContext

    backend = _SpyBackend()
    strategy = MultiAgentReviewStrategy()
    context = DecisionContext(
        run_id="run_test",
        episode_id="ep_test",
        step_id="stp_test",
        model=ModelRef(backend="fake.backend", provider="fake", model="scripted"),
        backend=backend,
        tools={},
        seed=7,
    )
    observation = {
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "side_to_move": "white",
        "move_number": 1,
        "history": [],
    }

    trace = await strategy.decide(observation, context)

    assert trace.declared_regime == "R5"
    assert trace.final_action == "e2e4"
    assert len(trace.calls) == 3
    assert [call.request_fingerprint for call in trace.calls] == [
        "chess-multi-agent:critical-scout:7",
        "chess-multi-agent:strategy-planner:7",
        "chess-multi-agent:final-reviewer:7",
    ]
    assert [call[1].fingerprint for call in backend.requests] == [
        "chess-multi-agent:critical-scout:7",
        "chess-multi-agent:strategy-planner:7",
        "chess-multi-agent:final-reviewer:7",
    ]
    assert trace.selection_rationale is not None
    assert trace.selection_rationale["workflow"] == [
        "critical_scout",
        "strategy_planner",
        "final_reviewer",
    ]
    assert trace.selection_rationale["critical_scout"]["hanging_pieces"]
    assert trace.selection_rationale["strategy_planner"]["preferred_move"] == "e2e4"
    assert trace.selection_rationale["final_reviewer"]["move"] == "e2e4"
    assert any(candidate.action == "e2e4" for candidate in trace.candidates)

    planner_prompt = backend.requests[1][0].messages[0].parts[0].text
    reviewer_prompt = backend.requests[2][0].messages[0].parts[0].text
    assert "critical_map" in planner_prompt
    assert "preferred_move" in reviewer_prompt


@pytest.mark.asyncio
async def test_reviewer_explicit_coordinate_move_wins_over_uci_tokens_in_explanation() -> None:
    from zugzwang_chess.strategies.multi_agent_review import MultiAgentReviewStrategy
    from zugzwang_core.ports.model import ModelRef
    from zugzwang_core.ports.strategy import DecisionContext

    backend = _SpyBackend()
    backend._outputs = (
        json.dumps(
            {
                "critical_map": "no immediate tactic",
                "hanging_pieces": [],
                "tactical_ideas": ["develop the knight"],
                "candidate_moves": ["g1f3"],
                "confidence": 0.8,
            }
        ),
        json.dumps(
            {
                "plan": "develop before a central break",
                "candidate_moves": ["g1f3"],
                "preferred_move": "Ng1f3",
                "risks": ["reject premature d2d4"],
            }
        ),
        json.dumps(
            {
                "move": "Ng1f3",
                "review": "Rejected premature d2d4; Ng1f3 is the reviewed move.",
                "critical_risks_addressed": ["development"],
                "confidence": 0.9,
            }
        ),
    )
    context = DecisionContext(
        run_id="run_test",
        episode_id="ep_test",
        step_id="stp_test",
        model=ModelRef(backend="fake.backend", provider="fake", model="scripted"),
        backend=backend,
        tools={},
        seed=7,
    )
    observation = {
        "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        "side_to_move": "white",
        "move_number": 2,
        "history": ["e2e4", "e7e5"],
    }

    trace = await MultiAgentReviewStrategy().decide(observation, context)

    assert trace.final_action == "g1f3"
