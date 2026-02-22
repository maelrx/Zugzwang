from __future__ import annotations

from zugzwang.knowledge.types import KnowledgeChunk


def load_endgame_chunks() -> list[KnowledgeChunk]:
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
