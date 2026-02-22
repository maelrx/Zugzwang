from __future__ import annotations

from zugzwang.knowledge.types import KnowledgeChunk


def load_eco_chunks() -> list[KnowledgeChunk]:
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
