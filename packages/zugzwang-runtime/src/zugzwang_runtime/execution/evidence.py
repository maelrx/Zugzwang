"""Small, deterministic helpers for first-class evidence artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from zugzwang_core.domain.artifacts import ArtifactPayload, ArtifactRef
from zugzwang_core.domain.canonical import canonical_json_bytes
from zugzwang_core.domain.clocks import to_iso_z, utc_now
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.ports.strategy import DecisionTrace

from ..artifacts.cas import ContentAddressedStore

_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "cookie",
    "set-cookie",
    "secret",
    "client_secret",
}


def sanitize_wire_payload(value: Any) -> Any:
    """Redact credential-shaped fields without rewriting scientific content."""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        return {
            str(key): "[REDACTED]"
            if str(key).lower() in _SECRET_KEYS
            else sanitize_wire_payload(item)
            for key, item in mapping.items()
        }
    if isinstance(value, (list, tuple)):
        sequence = cast(list[Any] | tuple[Any, ...], value)
        return [sanitize_wire_payload(item) for item in sequence]
    return value


def store_json_artifact(
    *,
    cas: ContentAddressedStore,
    writer: Any,
    payload: Any,
    media_type: str,
    redaction_policy: str | None = None,
) -> ArtifactRef:
    data = canonical_json_bytes(payload)
    return store_artifact(
        cas=cas,
        writer=writer,
        payload=ArtifactPayload(media_type=media_type, data=data),
        redaction_policy=redaction_policy,
    )


def store_artifact(
    *,
    cas: ContentAddressedStore,
    writer: Any,
    payload: ArtifactPayload,
    redaction_policy: str | None = None,
) -> ArtifactRef:
    ref = cas.put(
        payload,
        redaction_policy=redaction_policy,
    )
    from ..persistence.writer import InsertArtifactCommand

    writer.enqueue(
        InsertArtifactCommand(
            row={
                "artifact_id": ref.as_id(),
                "algorithm": "sha256",
                "size_bytes": len(payload.data),
                "media_type": payload.media_type,
                "relative_path": ref.storage_path(),
                "created_at": to_iso_z(utc_now()),
                "redaction_policy": redaction_policy,
            }
        )
    )
    return ref


def observation_artifact_payload(
    *,
    run_id: str,
    episode_id: str,
    step_id: str,
    state: Any,
    observation: dict[str, JsonValue],
    policy_settings: dict[str, JsonValue],
    declared_h: str,
    declared_k: str,
    state_ref: str | None,
) -> dict[str, JsonValue]:
    history_mode = "none"
    history_raw = policy_settings.get("history")
    if isinstance(history_raw, dict):
        mode = history_raw.get("mode")
        if isinstance(mode, str):
            history_mode = mode
    sources: dict[str, JsonValue] = {
        "fen": "fen" in observation,
        "history": history_mode,
        "image": "image" in observation,
        "legal_actions": "legal_actions" in observation,
    }
    return {
        "schema_version": "zgw.observation/v1",
        "run_id": run_id,
        "episode_id": episode_id,
        "step_id": step_id,
        "state_ref": state_ref or _state_fingerprint(state),
        "state_fingerprint": _state_fingerprint(state),
        "sources": sources,
        "policy": policy_settings,
        "payload": observation,
        "assistance": {"h": declared_h, "k": declared_k},
    }


def decision_trace_payload(
    *,
    run_id: str,
    episode_id: str,
    step_id: str,
    trace: DecisionTrace,
    attempt_index: int,
    gateway: Any = None,
    attempt_evidence: dict[str, dict[str, str | None]] | None = None,
) -> dict[str, JsonValue]:
    data = trace.model_dump(mode="json")
    refs: list[str] = []
    call_rows = data.get("calls")
    if isinstance(call_rows, list):
        call_items = cast(list[Any], call_rows)
        # ZGW-0103 R1: join by call identity only. A call whose evidence is
        # unknown keeps NO artifact refs — silently attaching another call's
        # response (the old reversed-order fallback) produced the 2.068/2.273
        # reference mismatches audited in the corpus dossier (§13).
        for call in call_items:
            if not isinstance(call, dict):
                continue
            call_data = cast(dict[str, Any], call)
            call_id = call_data.get("attempt_id")
            evidence = attempt_evidence.get(str(call_id), {}) if attempt_evidence else {}
            for field, ref in evidence.items():
                if ref:
                    call_data[field] = ref
                    refs.append(ref)
    stats = getattr(gateway, "stats", None)
    gateway_stats: dict[str, int] = (
        cast(dict[str, int], stats.as_dict())
        if stats is not None and hasattr(stats, "as_dict")
        else {}
    )
    data.update(
        {
            "schema_version": "zgw.decision-trace/v1",
            "run_id": run_id,
            "episode_id": episode_id,
            "step_id": step_id,
            "attempt_index": attempt_index,
            "gateway_stats": gateway_stats,
            "strategy": {
                "id": trace.strategy_id,
                "version": trace.strategy_version,
                "regime": trace.declared_regime,
            },
            "artifact_refs": sorted(set(refs)),
        }
    )
    return data


def _state_fingerprint(state: Any) -> str | None:
    value = getattr(state, "fingerprint", None)
    if callable(value):
        return str(value())
    return str(value) if value else None
