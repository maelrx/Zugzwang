from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from zugzwang.knowledge.embeddings import SparseVector, cosine_similarity, embed_text
from zugzwang.knowledge.types import KnowledgeChunk, RetrievedChunk


@dataclass(frozen=True)
class IndexedChunk:
    chunk: KnowledgeChunk
    vector: SparseVector


class InMemoryVectorDB:
    """Deterministic, dependency-free vector index for local RAG."""

    def __init__(self, embedding_fn: Callable[[str], SparseVector] | None = None) -> None:
        self._embedding_fn = embedding_fn or embed_text
        self._items: list[IndexedChunk] = []

    def add_chunks(self, chunks: Iterable[KnowledgeChunk]) -> None:
        for chunk in chunks:
            vector = self._embedding_fn(chunk.as_query_text())
            self._items.append(IndexedChunk(chunk=chunk, vector=vector))

    def search(
        self,
        query_text: str,
        *,
        top_k: int,
        min_similarity: float = 0.0,
        allowed_sources: set[str] | None = None,
        phase_hint: str | None = None,
    ) -> list[RetrievedChunk]:
        if top_k <= 0:
            return []
        query_vector = self._embedding_fn(query_text)
        if not query_vector:
            return []

        scored: list[RetrievedChunk] = []
        for item in self._items:
            if allowed_sources is not None and item.chunk.source not in allowed_sources:
                continue
            score = cosine_similarity(query_vector, item.vector)
            if phase_hint and item.chunk.phase == phase_hint:
                score += 0.03
            if score >= min_similarity:
                scored.append(RetrievedChunk(chunk=item.chunk, score=score))

        scored.sort(key=lambda entry: (-entry.score, entry.chunk.chunk_id))
        return scored[:top_k]
