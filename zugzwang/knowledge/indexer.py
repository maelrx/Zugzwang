from __future__ import annotations

from typing import Any, Callable

from zugzwang.knowledge.sources.eco import load_eco_chunks
from zugzwang.knowledge.sources.endgames import load_endgame_chunks
from zugzwang.knowledge.sources.lichess import load_lichess_chunks
from zugzwang.knowledge.types import KnowledgeChunk


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


def _enabled_source_names(flags: dict[str, bool]) -> list[str]:
    return [name for name in SOURCE_LOADERS if flags.get(name, False)]
