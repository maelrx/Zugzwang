from __future__ import annotations

import random
from dataclasses import dataclass

from zugzwang.core.board import BoardManager
from zugzwang.core.game import play_game
from zugzwang.core.players import LLMPlayer, RandomPlayer
from zugzwang.providers.base import ProviderResponse


def _strategy_config() -> dict:
    return {
        "use_system_prompt": True,
        "board_format": "fen",
        "provide_legal_moves": True,
        "provide_history": True,
        "history_plies": 8,
        "validation": {
            "feedback_level": "rich",
            "move_retries": 2,
            "provider_retries": 0,
            "provider_backoff_seconds": 0.0,
        },
    }


@dataclass
class _AlwaysInvalidProvider:
    calls: int = 0

    def complete(self, messages, model_config):  # type: ignore[no-untyped-def]
        _ = (messages, model_config)
        self.calls += 1
        return ProviderResponse(
            text="this is not a move",
            model="invalid-provider",
            input_tokens=8,
            output_tokens=5,
            latency_ms=3,
            cost_usd=0.0,
        )


def test_research_strict_returns_error_instead_of_random_fallback() -> None:
    provider = _AlwaysInvalidProvider()
    board = BoardManager()
    state = board.game_state([])

    player = LLMPlayer(
        name="llm",
        provider=provider,
        model="invalid-model",
        model_config={},
        protocol_mode="research_strict",
        strategy_config=_strategy_config(),
        rng=random.Random(13),
    )

    decision = player.choose_move(state)

    assert provider.calls == 3
    assert decision.provider_calls == 3
    assert decision.is_legal is False
    assert decision.parse_ok is False
    assert decision.move_uci is None
    assert decision.error in {"parse_failed", "validation_failed", "retries_exhausted"}


def test_research_strict_terminates_game_with_error() -> None:
    provider = _AlwaysInvalidProvider()
    white = RandomPlayer(name="random_white", rng=random.Random(21))
    black = LLMPlayer(
        name="llm_black",
        provider=provider,
        model="invalid-model",
        model_config={},
        protocol_mode="research_strict",
        strategy_config=_strategy_config(),
        rng=random.Random(22),
    )

    record = play_game(
        experiment_id="exp",
        game_number=1,
        config_hash="hash",
        seed=42,
        players_cfg={
            "white": {"type": "random", "name": "random_white"},
            "black": {"type": "llm", "name": "llm_black"},
        },
        white_player=white,
        black_player=black,
        protocol_mode="research_strict",
        max_plies=20,
    )

    assert record.termination == "error"
    assert record.result == "*"
    assert record.moves
    assert all(move.move_decision.error != "fallback_random" for move in record.moves)
    assert record.moves[-1].move_decision.move_uci is None
