from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source: str
    phase: str
    title: str
    content: str
    fen: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_query_text(self) -> str:
        parts = [self.title, self.content]
        if self.fen:
            parts.append(self.fen)
        if self.tags:
            parts.append(" ".join(self.tags))
        return " ".join(part for part in parts if part).strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: KnowledgeChunk
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
        }
