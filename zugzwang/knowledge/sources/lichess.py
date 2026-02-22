from __future__ import annotations

from zugzwang.knowledge.types import KnowledgeChunk


def load_lichess_chunks() -> list[KnowledgeChunk]:
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
