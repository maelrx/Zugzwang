from __future__ import annotations

import random
from dataclasses import dataclass

from zugzwang.agents.capability_moa import CapabilityMoaOrchestrator
from zugzwang.core.board import BoardManager
from zugzwang.core.players import LLMPlayer
from zugzwang.providers.base import ProviderResponse
from zugzwang.providers.mock import MockProvider


@dataclass
class _SequenceProvider:
    responses: list[str]
    calls: int = 0

    def complete(self, messages, model_config):  # type: ignore[no-untyped-def]
        idx = min(self.calls, len(self.responses) - 1)
        text = self.responses[idx]
        self.calls += 1
        return ProviderResponse(
            text=text,
            model=str(model_config.get("model", "seq")),
            input_tokens=4,
            output_tokens=1,
            latency_ms=3,
            cost_usd=0.001,
        )


def test_capability_moa_aggregator_move_is_used() -> None:
    provider = _SequenceProvider(responses=["e2e4", "d2d4", "e2e4"])
    orchestrator = CapabilityMoaOrchestrator(
        call_provider=lambda messages: provider.complete(messages, {"model": "seq"}),
        model="seq",
    )
    result = orchestrator.decide(
        base_prompt="Return one legal move in UCI.",
        legal_moves_uci=["e2e4", "d2d4", "g1f3"],
        proposer_roles=["reasoning", "compliance"],
    )
    assert result.parse_ok is True
    assert result.is_legal is True
    assert result.move_uci == "e2e4"
    assert result.provider_calls == 3
    assert len(result.traces) == 3
    assert result.aggregator_rationale is not None
    assert "Aggregator output accepted" in result.aggregator_rationale


def test_capability_moa_falls_back_to_proposer_majority() -> None:
    provider = _SequenceProvider(responses=["e2e4", "e2e4", "bad_output"])
    orchestrator = CapabilityMoaOrchestrator(
        call_provider=lambda messages: provider.complete(messages, {"model": "seq"}),
        model="seq",
    )
    result = orchestrator.decide(
        base_prompt="Return one legal move in UCI.",
        legal_moves_uci=["e2e4", "d2d4", "g1f3"],
        proposer_roles=["reasoning", "compliance"],
    )
    assert result.parse_ok is True
    assert result.is_legal is True
    assert result.move_uci == "e2e4"
    assert result.error == "moa_aggregator_invalid_fallback_candidate"
    assert result.aggregator_rationale is not None
    assert "fallback used" in result.aggregator_rationale


def test_llm_player_uses_capability_moa_when_enabled() -> None:
    board = BoardManager()
    state = board.game_state([])
    strategy = {
        "board_format": "fen",
        "provide_legal_moves": True,
        "provide_history": True,
        "history_plies": 8,
        "rag": {"enabled": False},
        "multi_agent": {
            "enabled": True,
            "mode": "capability_moa",
            "proposer_count": 2,
            "proposer_roles": ["reasoning", "compliance"],
        },
        "validation": {
            "feedback_level": "rich",
            "move_retries": 1,
            "provider_retries": 0,
            "provider_backoff_seconds": 0.0,
            "max_agentic_turns": 6,
        },
    }
    player = LLMPlayer(
        name="llm",
        provider=MockProvider(),
        model="mock-1",
        model_config={},
        protocol_mode="direct",
        strategy_config=strategy,
        rng=random.Random(5),
    )

    decision = player.choose_move(state)
    assert decision.parse_ok is True
    assert decision.is_legal is True
    assert decision.decision_mode == "capability_moa"
    assert decision.provider_calls == 3
    assert len(decision.agent_trace) == 3
    assert decision.aggregator_rationale is not None
