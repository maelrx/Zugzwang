from __future__ import annotations

from pathlib import Path

from zugzwang.knowledge.sources._shared import (
    DATA_ROOT,
    as_text,
    build_chunk_id,
    load_yaml_entries,
    normalize_phase,
    normalize_tags,
)
from zugzwang.knowledge.types import KnowledgeChunk


DATA_PATH = DATA_ROOT / "endgames" / "principles.yaml"


def load_endgame_chunks() -> list[KnowledgeChunk]:
    chunks = _load_from_yaml(DATA_PATH)
    if chunks:
        return chunks
    return _fallback_chunks()


def _load_from_yaml(path: Path) -> list[KnowledgeChunk]:
    entries = load_yaml_entries(path)
    chunks: list[KnowledgeChunk] = []
    for index, entry in enumerate(entries):
        endgame_type = as_text(entry.get("type")) or "Endgame Principle"
        material = as_text(entry.get("material"))
        principle = as_text(entry.get("principle"))
        technique = as_text(entry.get("technique"))
        if not principle:
            continue

        title = endgame_type if material is None else f"{endgame_type} ({material})"
        content_parts = [principle]
        if technique:
            content_parts.append(f"Technique: {technique}")
        content = " ".join(content_parts).strip()
        if not content:
            continue

        phase = normalize_phase(entry.get("phase"), default="endgame")
        chunk = KnowledgeChunk(
            chunk_id=build_chunk_id(
                source="endgames",
                index=index,
                explicit_id=entry.get("id"),
                title=title,
                extra=material,
            ),
            source="endgames",
            phase=phase,
            title=title,
            content=content,
            fen=as_text(entry.get("example_fen")) or as_text(entry.get("fen")),
            tags=normalize_tags(entry.get("tags"), defaults=("endgame", "principles")),
        )
        chunks.append(chunk)
    return chunks


def _fallback_chunks() -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id="endgame-kpk-opposition",
            source="endgames",
            phase="endgame",
            title="King and Pawn Opposition",
            content=(
                "In king and pawn endings, opposition often decides conversion."
                " Activate the king first and avoid rushing pawn pushes."
            ),
            tags=("endgame", "kpk", "opposition"),
        ),
        KnowledgeChunk(
            chunk_id="endgame-rook-behind-passed-pawn",
            source="endgames",
            phase="endgame",
            title="Rook Behind Passed Pawn",
            content=(
                "Rooks belong behind passed pawns, yours or the opponent's."
                " Keep rook activity and avoid passive defense when possible."
            ),
            tags=("endgame", "rook_endgame", "passed_pawn"),
        ),
        KnowledgeChunk(
            chunk_id="endgame-king-activity",
            source="endgames",
            phase="endgame",
            title="King Activity Priority",
            content=(
                "Central king activity is usually stronger than extra tempo moves."
                " Convert material advantage by improving king position."
            ),
            tags=("endgame", "king_activity"),
        ),
        KnowledgeChunk(
            chunk_id="endgame-bishop-knight-mating-net",
            source="endgames",
            phase="endgame",
            title="Minor Piece Coordination",
            content=(
                "Bishop and knight endings reward piece coordination and king support."
                " Avoid allowing outside passed pawns to distract both pieces."
            ),
            tags=("endgame", "minor_pieces", "coordination"),
        ),
        KnowledgeChunk(
            chunk_id="endgame-avoid-zugzwang-self",
            source="endgames",
            phase="endgame",
            title="Tempo Awareness",
            content=(
                "In reduced material positions, every pawn move can be irreversible."
                " Preserve useful waiting moves to avoid self-zugzwang."
            ),
            tags=("endgame", "zugzwang", "tempo"),
        ),
    ]
