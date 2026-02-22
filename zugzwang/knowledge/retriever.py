from __future__ import annotations

import hashlib
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from zugzwang.core.models import GameState
from zugzwang.knowledge.indexer import load_chunks, resolve_enabled_sources
from zugzwang.knowledge.types import RetrievedChunk
from zugzwang.knowledge.vectordb import InMemoryVectorDB


DEFAULT_MAX_CHUNKS = 3
DEFAULT_MAX_CHARS_PER_CHUNK = 260
DEFAULT_MIN_SIMILARITY = 0.08
DEFAULT_QUERY_CACHE_SIZE = 256

PHASE_ROUTING = {
    "opening": ("eco", "lichess"),
    "middlegame": ("lichess", "eco", "endgames"),
    "endgame": ("endgames", "lichess", "eco"),
}


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    latency_ms: int
    sources: list[str]


_DB_CACHE: dict[tuple[str, ...], InMemoryVectorDB] = {}
_QUERY_CACHE: dict[str, RetrievalResult] = {}


def query(game_state: GameState, retrieval_config: Any) -> RetrievalResult:
    if not _is_enabled(retrieval_config):
        return RetrievalResult(chunks=[], latency_ms=0, sources=[])

    enabled_sources = resolve_enabled_sources(retrieval_config)
    routed_sources = _routed_sources(_normalize_phase(game_state.phase), enabled_sources)
    if not routed_sources:
        return RetrievalResult(chunks=[], latency_ms=0, sources=[])

    max_chunks = _read_positive_int(retrieval_config, "max_chunks", default=DEFAULT_MAX_CHUNKS)
    min_similarity = _read_similarity_threshold(retrieval_config)
    query_cache_key = _query_cache_key(
        game_state=game_state,
        sources=routed_sources,
        max_chunks=max_chunks,
        min_similarity=min_similarity,
    )
    cached = _QUERY_CACHE.get(query_cache_key)
    if cached is not None:
        return cached

    started = perf_counter()
    vectordb = _get_or_create_db(routed_sources)
    fetched = vectordb.search(
        query_text=_build_query_text(game_state),
        top_k=max(max_chunks * 3, max_chunks),
        min_similarity=min_similarity,
        allowed_sources=set(routed_sources),
        phase_hint=_normalize_phase(game_state.phase),
    )
    selected = _phase_ranked_selection(
        chunks=fetched,
        phase=_normalize_phase(game_state.phase),
        max_chunks=max_chunks,
    )
    latency_ms = int((perf_counter() - started) * 1000)
    result = RetrievalResult(chunks=selected, latency_ms=latency_ms, sources=routed_sources)
    _put_query_cache(query_cache_key, result)
    return result


def _get_or_create_db(source_names: list[str]) -> InMemoryVectorDB:
    key = tuple(sorted(source_names))
    cached = _DB_CACHE.get(key)
    if cached is not None:
        return cached

    db = InMemoryVectorDB()
    db.add_chunks(load_chunks(source_names))
    _DB_CACHE[key] = db
    return db


def _build_query_text(game_state: GameState) -> str:
    history_tail = game_state.history_uci[-8:] if game_state.history_uci else []
    history_text = " ".join(history_tail)
    return (
        f"phase:{_normalize_phase(game_state.phase)} "
        f"fen:{game_state.fen} "
        f"active_color:{game_state.active_color} "
        f"move_number:{game_state.move_number} "
        f"history:{history_text}"
    )


def _phase_ranked_selection(
    chunks: list[RetrievedChunk],
    phase: str,
    max_chunks: int,
) -> list[RetrievedChunk]:
    phase_first = [chunk for chunk in chunks if chunk.chunk.phase == phase]
    fallback = [chunk for chunk in chunks if chunk.chunk.phase != phase]
    merged = [*phase_first, *fallback]
    return merged[:max_chunks]


def _is_enabled(retrieval_config: Any) -> bool:
    if not isinstance(retrieval_config, dict):
        return False
    return bool(retrieval_config.get("enabled", False))


def _normalize_phase(phase: str | None) -> str:
    if not isinstance(phase, str):
        return "middlegame"
    normalized = phase.strip().lower()
    if normalized not in PHASE_ROUTING:
        return "middlegame"
    return normalized


def _routed_sources(phase: str, enabled_sources: list[str]) -> list[str]:
    if not enabled_sources:
        return []
    phase_order = PHASE_ROUTING.get(phase, PHASE_ROUTING["middlegame"])
    prioritized = [source for source in phase_order if source in enabled_sources]
    leftovers = [source for source in enabled_sources if source not in prioritized]
    return [*prioritized, *leftovers]


def _read_positive_int(config: Any, key: str, default: int) -> int:
    if not isinstance(config, dict):
        return default
    value = config.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value > 0 else default
    if isinstance(value, float):
        casted = int(value)
        return casted if casted > 0 else default
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            casted = int(stripped)
            return casted if casted > 0 else default
    return default


def _read_similarity_threshold(config: Any) -> float:
    if not isinstance(config, dict):
        return DEFAULT_MIN_SIMILARITY
    value = config.get("min_similarity", DEFAULT_MIN_SIMILARITY)
    if isinstance(value, bool):
        return DEFAULT_MIN_SIMILARITY
    if isinstance(value, (int, float)):
        return min(1.0, max(0.0, float(value)))
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return DEFAULT_MIN_SIMILARITY
        return min(1.0, max(0.0, parsed))
    return DEFAULT_MIN_SIMILARITY


def _query_cache_key(
    game_state: GameState,
    sources: list[str],
    max_chunks: int,
    min_similarity: float,
) -> str:
    payload = "|".join(
        [
            game_state.fen,
            _normalize_phase(game_state.phase),
            ",".join(sources),
            str(max_chunks),
            f"{min_similarity:.4f}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _put_query_cache(key: str, result: RetrievalResult) -> None:
    if key in _QUERY_CACHE:
        _QUERY_CACHE[key] = result
        return
    if len(_QUERY_CACHE) >= DEFAULT_QUERY_CACHE_SIZE:
        oldest_key = next(iter(_QUERY_CACHE))
        _QUERY_CACHE.pop(oldest_key, None)
    _QUERY_CACHE[key] = result
