from __future__ import annotations

from zugzwang.strategy.validator import (
    build_retry_feedback,
    parse_first_uci,
    validate_move_response,
)


def test_parse_first_uci_extracts_move() -> None:
    assert parse_first_uci("best move is e2e4") == "e2e4"


def test_validate_move_response_parse_failure() -> None:
    result = validate_move_response("I think knight move", ["e2e4", "d2d4"])
    assert result.parse_ok is False
    assert result.is_legal is False
    assert result.error_code == "parse_failed"


def test_validate_move_response_illegal_move() -> None:
    result = validate_move_response("a2a4", ["e2e4", "d2d4"])
    assert result.parse_ok is True
    assert result.is_legal is False
    assert result.error_code == "illegal_move"


def test_build_retry_feedback_by_level() -> None:
    validation = validate_move_response("h2h4", ["e2e4", "d2d4"])

    minimal = build_retry_feedback(validation, "minimal", ["e2e4", "d2d4"], phase="opening")
    moderate = build_retry_feedback(validation, "moderate", ["e2e4", "d2d4"], phase="opening")
    rich = build_retry_feedback(validation, "rich", ["e2e4", "d2d4"], phase="opening")

    assert "legal UCI" in minimal
    assert "illegal" in moderate.lower()
    assert "Legal moves include" in rich
