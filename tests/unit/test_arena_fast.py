"""Luna-only Fast selection, persistence, and real factory wiring; offline."""

from __future__ import annotations

import time

import pytest

from tests.unit.test_arena_play import ScriptedBackend, _tool_call
from zugzwang_cli.arena.game import load_game
from zugzwang_cli.arena.providers import build_backend, providers_catalog
from zugzwang_cli.arena.server import ArenaService


def test_only_luna_catalog_exposes_fast() -> None:
    offered = [
        (p["id"], m["id"])
        for p in providers_catalog()
        for m in p["models"]
        if "fast" in m.get("service_tiers", [])
    ]
    assert offered == [("codex-cli", "gpt-5.6-luna")]


@pytest.mark.parametrize("tier", [None, "fast"])
def test_selected_tier_survives_reload_and_reaches_factory(tmp_path, tier) -> None:
    configs = []

    def factory(provider, **config):
        configs.append((provider, config))
        return ScriptedBackend(
            [[_tool_call("board_finalize", {"node_id": "n0", "action_id": "e7e5"})]]
        )

    service = ArenaService(tmp_path, backend_factory=factory)
    game = service.create_game(
        {"provider": "codex-cli", "model": "gpt-5.6-luna", "effort": "high", "service_tier": tier}
    )
    assert load_game(tmp_path / f"{game.game_id}.json").setup["service_tier"] == tier
    service.apply_move(game.game_id, "e2e4")
    for _ in range(300):
        if game.status != "model_thinking":
            break
        time.sleep(0.01)
    assert len(game.moves) == 2
    assert configs[0][1]["service_tier"] == tier
    assert configs[0][1]["effort"] == "high"


@pytest.mark.parametrize(
    "provider,model,tier",
    [
        ("opencode", "muse-spark-1.3-contributor", "fast"),
        ("codex-cli", "gpt-6-astra", "fast"),
        ("codex-cli", "gpt-5.6-luna", "invalid"),
    ],
)
def test_unsupported_fast_rejected_before_game_or_call(tmp_path, provider, model, tier) -> None:
    service = ArenaService(tmp_path)
    with pytest.raises(ValueError, match="apenas"):
        service.create_game({"provider": provider, "model": model, "service_tier": tier})
    assert not service.games
    assert not list(tmp_path.glob("arena-*"))


def test_factory_passes_fast_to_existing_codex_adapter(monkeypatch) -> None:
    import zgw_provider_codex_cli.adapter as module

    captured = []
    monkeypatch.setattr(module, "CodexCliBackend", lambda **config: captured.append(config))
    build_backend("codex-cli", model="gpt-5.6-luna", effort="high", service_tier="fast")
    assert captured[0]["service_tier"] == "fast"
    assert captured[0]["reasoning_effort"] == "high"
    build_backend("codex-cli", model="gpt-5.6-luna", effort="low")
    assert captured[1]["service_tier"] is None
