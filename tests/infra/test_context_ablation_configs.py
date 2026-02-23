from __future__ import annotations

from pathlib import Path

import pytest

from zugzwang.infra.config import resolve_with_hash


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("filename", "field_path", "expected"),
    [
        ("context_board_format_fen.yaml", "strategy.board_format", "fen"),
        ("context_board_format_ascii.yaml", "strategy.board_format", "ascii"),
        ("context_board_format_combined.yaml", "strategy.board_format", "combined"),
        ("context_board_format_unicode.yaml", "strategy.board_format", "unicode"),
        ("context_board_format_pgn.yaml", "strategy.board_format", "pgn"),
        ("context_legal_moves_on.yaml", "strategy.provide_legal_moves", True),
        ("context_legal_moves_off.yaml", "strategy.provide_legal_moves", False),
        ("context_history_on.yaml", "strategy.provide_history", True),
        ("context_history_off.yaml", "strategy.provide_history", False),
        ("context_history_plies_4.yaml", "strategy.history_plies", 4),
        ("context_history_plies_12.yaml", "strategy.history_plies", 12),
        ("protocol_direct.yaml", "protocol.mode", "direct"),
        ("protocol_research_strict.yaml", "protocol.mode", "research_strict"),
        ("protocol_agentic_compat.yaml", "protocol.mode", "agentic_compat"),
    ],
)
def test_context_and_protocol_ablation_configs_resolve(
    filename: str,
    field_path: str,
    expected: object,
) -> None:
    config_path = ROOT / "configs" / "ablations" / filename
    resolved, cfg_hash = resolve_with_hash(config_path)

    assert len(cfg_hash) == 64
    assert resolved["experiment"]["target_valid_games"] > 0

    cursor: object = resolved
    for part in field_path.split("."):
        assert isinstance(cursor, dict)
        assert part in cursor
        cursor = cursor[part]
    assert cursor == expected
