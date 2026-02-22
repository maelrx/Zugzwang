from __future__ import annotations

from typing import Any

from zugzwang.strategy.phase import normalize_phase


ALLOWED_MULTI_AGENT_MODES = {
    "capability_moa",
    "specialist_moa",
    "hybrid_phase_router",
}

ALLOWED_PROVIDER_POLICIES = {
    "shared_model",
    "role_model_overrides",
}

DEFAULT_PROPOSER_ROLES_BY_MODE = {
    "capability_moa": ["reasoning", "compliance", "safety"],
    "specialist_moa": ["tactical", "positional", "endgame"],
}

HYBRID_PHASE_ROLES = {
    "opening": ["positional", "compliance"],
    "middlegame": ["tactical", "positional", "compliance"],
    "endgame": ["endgame", "compliance"],
}


def normalize_multi_agent_mode(value: Any) -> str:
    if not isinstance(value, str):
        return "capability_moa"
    normalized = value.strip().lower()
    if normalized not in ALLOWED_MULTI_AGENT_MODES:
        return "capability_moa"
    return normalized


def normalize_provider_policy(value: Any) -> str:
    if not isinstance(value, str):
        return "shared_model"
    normalized = value.strip().lower()
    if normalized not in ALLOWED_PROVIDER_POLICIES:
        return "shared_model"
    return normalized


def resolve_proposer_roles(
    *,
    mode: str,
    phase: str | None,
    proposer_count: int,
    configured_roles: list[str] | None,
) -> list[str]:
    normalized_mode = normalize_multi_agent_mode(mode)
    roles = _configured_roles(configured_roles)
    if not roles:
        roles = _default_roles(normalized_mode, phase)

    if proposer_count <= 0:
        return roles
    if proposer_count <= len(roles):
        return roles[:proposer_count]
    # Preserve unique role sets; do not duplicate roles when requested count is larger.
    return roles


def resolve_model_override_for_role(
    *,
    role: str,
    provider_policy: str,
    role_models: dict[str, str] | None,
) -> str | None:
    if normalize_provider_policy(provider_policy) != "role_model_overrides":
        return None
    if not role_models:
        return None
    return role_models.get(role)


def _configured_roles(raw_roles: list[str] | None) -> list[str]:
    if not isinstance(raw_roles, list):
        return []
    normalized: list[str] = []
    for item in raw_roles:
        if not isinstance(item, str):
            continue
        role = item.strip().lower()
        if not role:
            continue
        normalized.append(role)
    return normalized


def _default_roles(mode: str, phase: str | None) -> list[str]:
    if mode == "hybrid_phase_router":
        normalized_phase = normalize_phase(phase)
        return list(HYBRID_PHASE_ROLES.get(normalized_phase, HYBRID_PHASE_ROLES["middlegame"]))
    return list(DEFAULT_PROPOSER_ROLES_BY_MODE.get(mode, DEFAULT_PROPOSER_ROLES_BY_MODE["capability_moa"]))
