from __future__ import annotations

from zugzwang.agents.router import (
    normalize_multi_agent_mode,
    normalize_provider_policy,
    resolve_model_override_for_role,
    resolve_proposer_roles,
)


def test_resolve_proposer_roles_hybrid_opening_defaults() -> None:
    roles = resolve_proposer_roles(
        mode="hybrid_phase_router",
        phase="opening",
        proposer_count=2,
        configured_roles=None,
    )
    assert roles == ["positional", "compliance"]


def test_resolve_proposer_roles_specialist_defaults() -> None:
    roles = resolve_proposer_roles(
        mode="specialist_moa",
        phase="middlegame",
        proposer_count=3,
        configured_roles=None,
    )
    assert roles == ["tactical", "positional", "endgame"]


def test_resolve_proposer_roles_does_not_duplicate_roles_when_count_exceeds_set() -> None:
    roles = resolve_proposer_roles(
        mode="hybrid_phase_router",
        phase="opening",
        proposer_count=3,
        configured_roles=None,
    )
    assert roles == ["positional", "compliance"]


def test_resolve_model_override_for_role_policy() -> None:
    override = resolve_model_override_for_role(
        role="aggregator",
        provider_policy="role_model_overrides",
        role_models={"aggregator": "model-agg"},
    )
    assert override == "model-agg"
    assert (
        resolve_model_override_for_role(
            role="aggregator",
            provider_policy="shared_model",
            role_models={"aggregator": "model-agg"},
        )
        is None
    )


def test_normalizers_fallback_to_defaults() -> None:
    assert normalize_multi_agent_mode("unknown") == "capability_moa"
    assert normalize_provider_policy("unknown") == "shared_model"
