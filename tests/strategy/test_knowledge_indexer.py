from __future__ import annotations

from zugzwang.knowledge.indexer import build_index, load_chunks


def test_build_index_loads_all_rag_sources() -> None:
    db, summary = build_index(["eco", "lichess", "endgames"])

    assert summary.chunk_count > 0
    assert summary.chunk_count_by_source["eco"] > 0
    assert summary.chunk_count_by_source["lichess"] > 0
    assert summary.chunk_count_by_source["endgames"] > 0
    assert summary.chunk_count_by_phase["opening"] > 0
    assert summary.chunk_count_by_phase["middlegame"] > 0
    assert summary.chunk_count_by_phase["endgame"] > 0

    results = db.search(
        query_text="king opposition and passed pawn conversion in rook endings",
        top_k=3,
        min_similarity=0.01,
        allowed_sources={"endgames"},
        phase_hint="endgame",
    )
    assert results
    assert all(item.chunk.source == "endgames" for item in results)


def test_load_chunks_handles_unknown_sources_gracefully() -> None:
    chunks = load_chunks(["eco", "unknown_source", "lichess"])

    assert chunks
    assert any(chunk.source == "eco" for chunk in chunks)
    assert any(chunk.source == "lichess" for chunk in chunks)
