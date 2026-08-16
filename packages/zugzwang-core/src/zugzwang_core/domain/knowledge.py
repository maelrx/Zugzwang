"""Static KnowledgePacket contract (ADR-035, ADR-047).

A KnowledgePacket is a versioned static artifact used to test causal knowledge
injection without retrieval infrastructure. The canonical model mirrors
``schemas/knowledge-packet.schema.json``; content hashes enter the condition
identity so any packet edit changes the protocol fingerprint.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .assistance import KClass
from .canonical import hash_canonical

PACKET_SCHEMA_VERSION = "0.1.0"

_FORBIDDEN_MARKERS_BELOW_K7 = ("best move is", "main line is", "\u00b1", "\u2213", " cp ")


class PacketScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: Literal["chess"] = "chess"
    phases: tuple[str, ...] = ()
    structures: tuple[str, ...] = ()
    openings: tuple[str, ...] = ()


class PacketContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    principles: tuple[str, ...] = Field(min_length=1)
    candidate_plans: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()

    def body_text(self) -> str:
        lines: list[str] = ["Principles:"]
        lines.extend(f"- {line}" for line in self.principles)
        if self.candidate_plans:
            lines.append("Candidate plans:")
            lines.extend(f"- {line}" for line in self.candidate_plans)
        if self.failure_modes:
            lines.append("Failure modes to avoid:")
            lines.extend(f"- {line}" for line in self.failure_modes)
        return "\n".join(lines)


class PacketLeakage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    current_position_analysis: bool = False
    target_move: bool = False
    engine_evaluation: bool = False
    transposition_lookup: bool = False


class PacketProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    curator: str
    sources: tuple[str, ...] = Field(min_length=1)
    license: str
    created_at: str


class KnowledgePacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["0.1.0"] = PACKET_SCHEMA_VERSION
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    version: str
    title: str
    language: str = "en"
    knowledge_class: str = Field(pattern=r"^K[0-7]$")
    scope: PacketScope
    applicability: dict[str, Any] = Field(default_factory=dict)
    content: PacketContent
    leakage: PacketLeakage = PacketLeakage()
    provenance: PacketProvenance
    content_hash: str = Field(default="", pattern=r"^([0-9a-f]{64})?$")

    @property
    def k_class(self) -> KClass:
        return KClass[self.knowledge_class]

    def rendered_body(self) -> str:
        return self.content.body_text()

    def self_hash(self) -> str:
        """Canonical hash of the whole packet except the hash field itself."""
        return hash_canonical(
            {
                "schema_version": self.schema_version,
                "id": self.id,
                "version": self.version,
                "title": self.title,
                "language": self.language,
                "knowledge_class": self.knowledge_class,
                "scope": self.scope.model_dump(mode="json"),
                "applicability": self.applicability,
                "content": self.content.model_dump(mode="json"),
                "leakage": self.leakage.model_dump(mode="json"),
                "provenance": self.provenance.model_dump(mode="json"),
            }
        )

    def with_content_hash(self) -> KnowledgePacket:
        """Return a copy with the content hash filled (protocol identity input)."""
        return self.model_copy(update={"content_hash": self.self_hash()})

    def audit_leakage(self) -> tuple[str, ...]:
        """Deterministic leakage audit: declared leakage flags plus marker scan.

        Content below K7 must not carry engine-eval markers; declared leakage
        flags are surfaced as audit notes, not failures.
        """
        violations: list[str] = []
        body = self.rendered_body().lower()
        if self.k_class < KClass.K7:
            for marker in _FORBIDDEN_MARKERS_BELOW_K7:
                if marker in body:
                    violations.append(f"engine marker {marker!r} in K<7 packet")
        declared: list[str] = []
        if self.leakage.current_position_analysis:
            declared.append("current_position_analysis")
        if self.leakage.target_move:
            declared.append("target_move")
        if self.leakage.engine_evaluation:
            declared.append("engine_evaluation")
        if self.leakage.transposition_lookup:
            declared.append("transposition_lookup")
        if declared and self.k_class < KClass.K7:
            violations.append(f"leakage flags declared on K<7 packet: {', '.join(declared)}")
        return tuple(violations)


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate for token-matching controls (S5/S6)."""
    return max(1, (len(text) + 3) // 4)
