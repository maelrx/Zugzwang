from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from zugzwang.knowledge.sources.eco import load_eco_chunks
from zugzwang.knowledge.sources.endgames import load_endgame_chunks
from zugzwang.knowledge.sources.lichess import load_lichess_chunks
from zugzwang.knowledge.types import KnowledgeChunk
from zugzwang.knowledge.vectordb import InMemoryVectorDB


SourceLoader = Callable[[], list[KnowledgeChunk]]


SOURCE_LOADERS: dict[str, SourceLoader] = {
    "eco": load_eco_chunks,
    "lichess": load_lichess_chunks,
    "endgames": load_endgame_chunks,
}


DEFAULT_SOURCE_FLAGS: dict[str, bool] = {
    "eco": True,
    "lichess": True,
    "endgames": True,
}


@dataclass(frozen=True)
class KnowledgeIndexSummary:
    source_names: list[str]
    chunk_count: int
    chunk_count_by_source: dict[str, int]
    chunk_count_by_phase: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_enabled_sources(retrieval_config: Any) -> list[str]:
    flags = dict(DEFAULT_SOURCE_FLAGS)
    if not isinstance(retrieval_config, dict):
        return _enabled_source_names(flags)

    sources = retrieval_config.get("sources")
    if isinstance(sources, list) and sources:
        flags = {name: False for name in SOURCE_LOADERS}
        for source_name in sources:
            if not isinstance(source_name, str):
                continue
            key = source_name.strip().lower()
            if key in flags:
                flags[key] = True

    include_sources = retrieval_config.get("include_sources")
    if isinstance(include_sources, dict):
        for source_name, enabled in include_sources.items():
            if not isinstance(source_name, str):
                continue
            key = source_name.strip().lower()
            if key in flags:
                flags[key] = bool(enabled)

    return _enabled_source_names(flags)


def load_chunks(source_names: list[str]) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for source_name in source_names:
        loader = SOURCE_LOADERS.get(source_name)
        if loader is None:
            continue
        chunks.extend(loader())
    return chunks


def build_index(source_names: list[str] | None = None) -> tuple[InMemoryVectorDB, KnowledgeIndexSummary]:
    selected = _normalize_source_list(source_names)
    chunks = load_chunks(selected)
    db = InMemoryVectorDB()
    db.add_chunks(chunks)
    summary = _build_summary(selected, chunks)
    return db, summary


def _normalize_source_list(source_names: list[str] | None) -> list[str]:
    if not source_names:
        return list(SOURCE_LOADERS.keys())
    selected: list[str] = []
    for item in source_names:
        if not isinstance(item, str):
            continue
        key = item.strip().lower()
        if key in SOURCE_LOADERS and key not in selected:
            selected.append(key)
    if not selected:
        return list(SOURCE_LOADERS.keys())
    return selected


def _build_summary(
    source_names: list[str],
    chunks: list[KnowledgeChunk],
) -> KnowledgeIndexSummary:
    by_source = {name: 0 for name in source_names}
    by_phase = {"opening": 0, "middlegame": 0, "endgame": 0}
    for chunk in chunks:
        by_source[chunk.source] = by_source.get(chunk.source, 0) + 1
        by_phase[chunk.phase] = by_phase.get(chunk.phase, 0) + 1

    return KnowledgeIndexSummary(
        source_names=list(source_names),
        chunk_count=len(chunks),
        chunk_count_by_source=by_source,
        chunk_count_by_phase=by_phase,
    )


def _enabled_source_names(flags: dict[str, bool]) -> list[str]:
    return [name for name in SOURCE_LOADERS if flags.get(name, False)]
