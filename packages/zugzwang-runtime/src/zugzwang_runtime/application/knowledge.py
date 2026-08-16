"""Knowledge packet loading (ZGW-0074).

Packets live next to the manifest that references them:
``<manifest_dir>/knowledge/<ref>.yaml`` (or .json). Loading is deterministic:
files are validated against the canonical KnowledgePacket model, content
hashes are computed and every referenced id must resolve exactly once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from zugzwang_core.domain.errors import ManifestValidationError
from zugzwang_core.domain.knowledge import KnowledgePacket


def load_knowledge_packets(
    manifest_path: Path,
    refs: tuple[str, ...],
) -> tuple[KnowledgePacket, ...]:
    """Resolve packet references relative to the manifest directory."""
    if not refs:
        return ()
    manifest_dir = manifest_path.resolve().parent
    packets: list[KnowledgePacket] = []
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            raise ManifestValidationError(f"knowledge packet {ref!r} referenced twice")
        seen.add(ref)
        packet = _load_one(manifest_dir, ref)
        violations = packet.audit_leakage()
        if violations:
            raise ManifestValidationError(
                f"knowledge packet {ref!r} failed leakage audit",
                technical_context="; ".join(violations),
            )
        packets.append(packet.with_content_hash())
    return tuple(packets)


def _load_one(manifest_dir: Path, ref: str) -> KnowledgePacket:
    for suffix in (".yaml", ".yml", ".json"):
        candidate = manifest_dir / "knowledge" / f"{ref}{suffix}"
        if candidate.is_file():
            return _parse(candidate, ref)
    raise ManifestValidationError(
        f"knowledge packet {ref!r} not found",
        technical_context=f"searched {manifest_dir / 'knowledge'} for {ref}.yaml|.yml|.json",
    )


def _parse(path: Path, ref: str) -> KnowledgePacket:
    data: Any
    try:
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            data = loaded if isinstance(loaded, dict) else {}
    except Exception as exc:
        raise ManifestValidationError(
            f"knowledge packet {ref!r} unreadable", technical_context=str(exc)
        ) from exc
    if not isinstance(data, dict):
        raise ManifestValidationError(f"knowledge packet {ref!r} must be a mapping")
    packet_raw = data.get("packet")
    if not isinstance(packet_raw, dict):
        raise ManifestValidationError(f"knowledge packet {ref!r} missing 'packet' key")
    try:
        return KnowledgePacket.model_validate(packet_raw)
    except Exception as exc:
        raise ManifestValidationError(
            f"knowledge packet {ref!r} failed validation", technical_context=str(exc)[:300]
        ) from exc
