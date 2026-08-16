"""Knowledge packet rendering for chess strategies (ZGW-0074).

Format is versioned: any change to how packets are rendered must bump
KNOWLEDGE_RENDER_VERSION so protocol traces stay reproducible.
"""

from __future__ import annotations

from typing import Any

from zugzwang_core.domain.assistance import AssistanceImpact, HClass
from zugzwang_core.domain.knowledge import KnowledgePacket

KNOWLEDGE_RENDER_VERSION = "1"


def render_knowledge_section(packets: tuple[Any, ...]) -> str:
    """Render resolved packets as a deterministic prompt section (empty if none)."""
    if not packets:
        return ""
    blocks: list[str] = []
    for raw in packets:
        if not isinstance(raw, KnowledgePacket):
            continue
        blocks.append(
            f"### Knowledge ({raw.id} v{raw.version} K{raw.knowledge_class[1:]} "
            f"hash={raw.content_hash[:12]})\n{raw.rendered_body()}"
        )
    if not blocks:
        return ""
    return "The following expert knowledge applies to this position:\n\n" + "\n\n".join(blocks)


def knowledge_impacts(packets: tuple[Any, ...]) -> tuple[AssistanceImpact, ...]:
    """One AssistanceImpact per injected packet (K axis only)."""
    impacts: list[AssistanceImpact] = []
    for raw in packets:
        if isinstance(raw, KnowledgePacket):
            impacts.append(
                AssistanceImpact(h=HClass.H0, k=raw.k_class, source=f"knowledge:{raw.id}")
            )
    return tuple(impacts)
