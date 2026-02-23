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


DATA_PATH = DATA_ROOT / "openings" / "eco_book.yaml"


def load_eco_chunks() -> list[KnowledgeChunk]:
    chunks = _load_from_yaml(DATA_PATH)
    if chunks:
        return chunks
    return _fallback_chunks()


def _load_from_yaml(path: Path) -> list[KnowledgeChunk]:
    entries = load_yaml_entries(path)
    chunks: list[KnowledgeChunk] = []
    for index, entry in enumerate(entries):
        eco = as_text(entry.get("eco"))
        name = as_text(entry.get("name"))
        moves = as_text(entry.get("moves"))
        plan = as_text(entry.get("plan")) or as_text(entry.get("description"))
        if not name or not plan:
            continue

        title = f"{name} ({eco})" if eco else name
        content_parts = []
        if moves:
            content_parts.append(f"Moves: {moves}.")
        content_parts.append(plan)
        content = " ".join(content_parts).strip()
        if not content:
            continue

        phase = normalize_phase(entry.get("phase"), default="opening")
        chunk = KnowledgeChunk(
            chunk_id=build_chunk_id(
                source="eco",
                index=index,
                explicit_id=entry.get("id"),
                title=title,
                extra=eco or moves,
            ),
            source="eco",
            phase=phase,
            title=title,
            content=content,
            fen=as_text(entry.get("key_fen")) or as_text(entry.get("fen")),
            tags=normalize_tags(entry.get("tags"), defaults=("opening", "eco")),
        )
        chunks.append(chunk)
    return chunks


def _fallback_chunks() -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id="eco-c20-kings-pawn",
            source="eco",
            phase="opening",
            title="King's Pawn Game (C20)",
            content=(
                "Against 1.e4, prioritize central control and quick development."
                " Contest e4 with ...e5 or ...c5 and avoid early queen moves."
            ),
            tags=("opening", "center", "development"),
        ),
        KnowledgeChunk(
            chunk_id="eco-b20-sicilian",
            source="eco",
            phase="opening",
            title="Sicilian Defence (B20)",
            content=(
                "After 1.e4 c5, seek asymmetry and queenside counterplay."
                " Develop knights before committing central pawn breaks."
            ),
            tags=("opening", "sicilian", "counterplay"),
        ),
        KnowledgeChunk(
            chunk_id="eco-c50-italian",
            source="eco",
            phase="opening",
            title="Italian Game (C50)",
            content=(
                "In open e4 e5 structures, guard f7 and keep king safety high."
                " Complete kingside development before tactical pawn grabs."
            ),
            tags=("opening", "italian", "king_safety"),
        ),
        KnowledgeChunk(
            chunk_id="eco-c00-french",
            source="eco",
            phase="opening",
            title="French Defence (C00)",
            content=(
                "The French structure favors a resilient center with ...e6 and ...d5."
                " Watch for light-squared weaknesses and timely ...c5 breaks."
            ),
            tags=("opening", "french", "pawn_structure"),
        ),
        KnowledgeChunk(
            chunk_id="eco-d00-queens-pawn",
            source="eco",
            phase="opening",
            title="Queen's Pawn Structures (D00)",
            content=(
                "Versus 1.d4, challenge the center early with ...d5 or ...Nf6."
                " Piece activity and pawn breaks ...c5 or ...e5 define equality chances."
            ),
            tags=("opening", "queens_pawn", "center"),
        ),
        KnowledgeChunk(
            chunk_id="eco-e60-kings-indian",
            source="eco",
            phase="opening",
            title="King's Indian Plans (E60)",
            content=(
                "In King's Indian setups, prioritize king safety and pawn lever timing."
                " Typical counterplay includes ...e5 or ...c5 and queenside pressure."
            ),
            tags=("opening", "kings_indian", "plans"),
        ),
    ]
