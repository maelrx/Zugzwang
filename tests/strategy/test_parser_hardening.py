from __future__ import annotations

from zugzwang.strategy.validator import normalize_uci_response, validate_move_response


def test_normalize_uci_response_accepts_common_variants() -> None:
    assert normalize_uci_response("e2e4") == "e2e4"
    assert normalize_uci_response("E2E4") == "e2e4"
    assert normalize_uci_response("e2-e4") == "e2e4"
    assert normalize_uci_response("e2 e4") == "e2e4"
    assert normalize_uci_response("I choose e2e4") == "e2e4"


def test_validate_move_response_can_parse_san_when_fen_is_available() -> None:
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    legal_moves = ["g1f3", "e2e4", "d2d4"]

    result = validate_move_response("Nf3", legal_moves, fen=fen)
    assert result.parse_ok is True
    assert result.is_legal is True
    assert result.move_uci == "g1f3"

    result_phrase = validate_move_response("I choose Nf3", legal_moves, fen=fen)
    assert result_phrase.parse_ok is True
    assert result_phrase.is_legal is True
    assert result_phrase.move_uci == "g1f3"


def test_validate_move_response_keeps_parse_failure_for_gibberish() -> None:
    legal_moves = ["e2e4", "d2d4"]
    result = validate_move_response("some random words", legal_moves, fen=None)
    assert result.parse_ok is False
    assert result.is_legal is False
    assert result.error_code == "parse_failed"
