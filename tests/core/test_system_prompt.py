from __future__ import annotations

import random
from dataclasses import dataclass, field

from zugzwang.core.board import BoardManager
from zugzwang.core.players import LLMPlayer
from zugzwang.providers.base import ProviderResponse


@dataclass
class _CaptureMessagesProvider:
    messages_history: list[list[dict[str, str]]] = field(default_factory=list)

    def complete(self, messages, model_config):  # type: ignore[no-untyped-def]
        _ = model_config
        self.messages_history.append(list(messages))
        return ProviderResponse(
            text="e2e4",
            model="capture-provider",
            input_tokens=10,
            output_tokens=1,
            latency_ms=2,
            cost_usd=0.0,
        )


def _base_strategy() -> dict:
    return {
        "board_format": "fen",
        "provide_legal_moves": True,
        "provide_history": True,
        "history_plies": 8,
        "validation": {
            "feedback_level": "rich",
            "move_retries": 0,
            "provider_retries": 0,
            "provider_backoff_seconds": 0.0,
        },
    }


def test_use_system_prompt_sends_system_and_user_messages() -> None:
    provider = _CaptureMessagesProvider()
    board = BoardManager()
    state = board.game_state([])

    strategy = _base_strategy()
    strategy["use_system_prompt"] = True

    player = LLMPlayer(
        name="llm",
        provider=provider,
        model="capture-model",
        model_config={},
        protocol_mode="direct",
        strategy_config=strategy,
        rng=random.Random(3),
    )
    decision = player.choose_move(state)

    assert decision.parse_ok is True
    assert provider.messages_history
    sent = provider.messages_history[-1]
    assert len(sent) == 2
    assert sent[0]["role"] == "system"
    assert sent[1]["role"] == "user"
    assert "FEN:" in sent[1]["content"]
    assert "legal move in UCI format" in sent[0]["content"]


def test_without_system_prompt_sends_single_user_message() -> None:
    provider = _CaptureMessagesProvider()
    board = BoardManager()
    state = board.game_state([])

    strategy = _base_strategy()
    strategy["use_system_prompt"] = False

    player = LLMPlayer(
        name="llm",
        provider=provider,
        model="capture-model",
        model_config={},
        protocol_mode="direct",
        strategy_config=strategy,
        rng=random.Random(4),
    )
    decision = player.choose_move(state)

    assert decision.parse_ok is True
    sent = provider.messages_history[-1]
    assert len(sent) == 1
    assert sent[0]["role"] == "user"
    assert "You are a chess assistant" in sent[0]["content"]
    assert "FEN:" in sent[0]["content"]
