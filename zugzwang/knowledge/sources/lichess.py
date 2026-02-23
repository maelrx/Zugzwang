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


DATA_PATH = DATA_ROOT / "tactics" / "patterns.yaml"


def load_lichess_chunks() -> list[KnowledgeChunk]:
    chunks = _load_from_yaml(DATA_PATH)
    if chunks:
        return chunks
    return _fallback_chunks()


def _load_from_yaml(path: Path) -> list[KnowledgeChunk]:
    entries = load_yaml_entries(path)
    chunks: list[KnowledgeChunk] = []
    for index, entry in enumerate(entries):
        title = as_text(entry.get("title")) or as_text(entry.get("theme"))
        description = as_text(entry.get("description"))
        principle = as_text(entry.get("principle"))
        solution = as_text(entry.get("solution"))
        if not title or not (description or principle):
            continue

        content_parts = []
        if description:
            content_parts.append(description)
        if principle:
            content_parts.append(f"Principle: {principle}")
        if solution:
            content_parts.append(f"Typical continuation: {solution}")
        content = " ".join(content_parts).strip()
        if not content:
            continue

        phase = normalize_phase(entry.get("phase"), default="middlegame")
        theme = as_text(entry.get("theme"))
        chunk = KnowledgeChunk(
            chunk_id=build_chunk_id(
                source="lichess",
                index=index,
                explicit_id=entry.get("id"),
                title=title,
                extra=theme or phase,
            ),
            source="lichess",
            phase=phase,
            title=title,
            content=content,
            fen=as_text(entry.get("example_fen")) or as_text(entry.get("fen")),
            tags=normalize_tags(entry.get("tags"), defaults=("tactics", theme or "pattern")),
        )
        chunks.append(chunk)
    return chunks


def _fallback_chunks() -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id="lichess-forcing-sequence",
            source="lichess",
            phase="middlegame",
            title="Checks, Captures, Threats",
            content=(
                "Before choosing a quiet move, scan forcing options: checks, captures,"
                " and direct threats. Tactical sequences can override strategic plans."
            ),
            tags=("middlegame", "tactics", "forcing_moves"),
        ),
        KnowledgeChunk(
            chunk_id="lichess-king-safety",
            source="lichess",
            phase="middlegame",
            title="King Safety First",
            content=(
                "When kings are exposed, prioritize lines that open checks and attack weak squares."
                " Avoid creating your own back-rank weaknesses."
            ),
            tags=("middlegame", "king_safety", "attack"),
        ),
        KnowledgeChunk(
            chunk_id="lichess-piece-activity",
            source="lichess",
            phase="middlegame",
            title="Improve Worst Piece",
            content=(
                "If no tactic is available, improve the least active piece and coordinate rooks."
                " Avoid repeating moves without concrete gain."
            ),
            tags=("middlegame", "piece_activity", "planning"),
        ),
        KnowledgeChunk(
            chunk_id="lichess-pawn-breaks",
            source="lichess",
            phase="middlegame",
            title="Pawn Break Timing",
            content=(
                "Use pawn breaks to challenge the center or open files for rooks."
                " Prepare the break with piece support before committing."
            ),
            tags=("middlegame", "pawn_break", "center"),
        ),
        KnowledgeChunk(
            chunk_id="lichess-opening-development",
            source="lichess",
            phase="opening",
            title="Opening Development Rules",
            content=(
                "Develop minor pieces efficiently, castle early, and avoid moving the same piece repeatedly."
                " Contest center squares with pawns and pieces."
            ),
            tags=("opening", "development", "king_safety"),
        ),
        KnowledgeChunk(
            chunk_id="lichess-endgame-passed-pawn",
            source="lichess",
            phase="endgame",
            title="Passed Pawn Technique",
            content=(
                "Create and support passed pawns with king and rook coordination."
                " Fix opponent pawns before pushing your passer."
            ),
            tags=("endgame", "passed_pawn", "conversion"),
        ),
    ]
