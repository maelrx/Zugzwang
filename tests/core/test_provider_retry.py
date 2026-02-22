from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from zugzwang.core.board import BoardManager
from zugzwang.core.players import LLMPlayer
from zugzwang.providers.base import ProviderError, ProviderResponse


def _strategy_config() -> dict[str, Any]:
    return {
        "board_format": "fen",
        "provide_legal_moves": True,
        "provide_history": True,
        "history_plies": 8,
        "validation": {
            "feedback_level": "rich",
            "move_retries": 3,
            "provider_retries": 3,
            "provider_backoff_seconds": 0.0,
            "max_agentic_turns": 6,
        },
    }


def _initial_state():
    board = BoardManager()
    return board.game_state([])


@dataclass
class _AuthErrorProvider:
    calls: int = 0

    def complete(self, messages: list[dict[str, str]], model_config: dict[str, Any]) -> ProviderResponse:
        self.calls += 1
        raise ProviderError(
            "Unauthorized",
            category="auth",
            retryable=False,
            status_code=401,
        )


@dataclass
class _FlakyProvider:
    calls: int = 0

    def complete(self, messages: list[dict[str, str]], model_config: dict[str, Any]) -> ProviderResponse:
        self.calls += 1
        if self.calls == 1:
            raise ProviderError("timeout", category="timeout", retryable=True)
        return ProviderResponse(
            text="e2e4",
            model="flaky-1",
            input_tokens=10,
            output_tokens=2,
            latency_ms=5,
        )


def test_non_retryable_provider_error_stops_fast() -> None:
    provider = _AuthErrorProvider()
    player = LLMPlayer(
        name="llm",
        provider=provider,
        model="x",
        model_config={},
        protocol_mode="direct",
        strategy_config=_strategy_config(),
        rng=random.Random(7),
    )

    decision = player.choose_move(_initial_state())

    assert provider.calls == 1
    assert decision.provider_calls == 0
    assert decision.parse_ok is False
    assert decision.error == "provider_auth"


def test_retryable_provider_error_is_retried() -> None:
    provider = _FlakyProvider()
    player = LLMPlayer(
        name="llm",
        provider=provider,
        model="x",
        model_config={},
        protocol_mode="direct",
        strategy_config=_strategy_config(),
        rng=random.Random(7),
    )

    decision = player.choose_move(_initial_state())

    assert provider.calls == 2
    assert decision.provider_calls == 1
    assert decision.parse_ok is True
    assert decision.move_uci == "e2e4"
