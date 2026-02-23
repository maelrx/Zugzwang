from __future__ import annotations

import random

from zugzwang.core.players import LLMPlayer, build_player
from zugzwang.providers.model_routing import resolve_provider_and_model


def test_resolve_provider_and_model_kimi_k25_aliases() -> None:
    provider, model = resolve_provider_and_model("kimi", "kimi-2.5")
    assert provider == "kimicode"
    assert model == "kimi-for-coding"

    provider, model = resolve_provider_and_model("kimicode", "k2.5")
    assert provider == "kimicode"
    assert model == "kimi-for-coding"


def test_build_player_routes_kimi_25_to_kimicode(monkeypatch) -> None:
    calls: list[str] = []

    class FakeProvider:
        def complete(self, messages, model_config):  # type: ignore[no-untyped-def]
            _ = (messages, model_config)
            raise RuntimeError("not used in this unit test")

    def fake_create_provider(provider_name: str):  # type: ignore[no-untyped-def]
        calls.append(provider_name)
        return FakeProvider()

    monkeypatch.setattr("zugzwang.core.players.create_provider", fake_create_provider)

    player = build_player(
        player_config={
            "type": "llm",
            "name": "llm_black",
            "provider": "kimi",
            "model": "kimi-2.5",
        },
        protocol_mode="direct",
        strategy_config={},
        rng=random.Random(7),
    )

    assert calls == ["kimicode"]
    assert isinstance(player, LLMPlayer)
    assert player.model == "kimi-for-coding"
