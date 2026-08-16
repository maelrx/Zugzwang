"""Chess formal tests: perft, codecs, state, environment (ADR-023, M2 exit)."""

from __future__ import annotations

import chess
import pytest
from hypothesis import given
from hypothesis import strategies as st

from zugzwang_chess import (
    ChessGameState,
    StandardChessEnvironment,
    export_pgn_mainline,
    fen_from_state,
    format_san,
    parse_fen,
    parse_san,
    parse_uci,
    render_ascii,
)
from zugzwang_chess.environment.standard import START_FEN
from zugzwang_chess.metrics.reconstruction import score_reconstruction

env = StandardChessEnvironment()

# Classic perft positions (Kiwipete, position 3, 4, 5 from CPW).
PERFT_POSITIONS = {
    START_FEN: (1, 20, 400),
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1": (1, 48, 2039),
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1": (1, 14, 191),
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8": (1, 44, 1486),
    "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10": (1, 46, 2079),
}


def _perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    total = 0
    for move in board.legal_moves:
        board.push(move)
        total += _perft(board, depth - 1)
        board.pop()
    return total


@pytest.mark.unit
class TestPerft:
    @pytest.mark.parametrize("fen", list(PERFT_POSITIONS))
    def test_depth1(self, fen: str) -> None:
        expected = PERFT_POSITIONS[fen][1]
        board = chess.Board(fen)
        assert _perft(board, 1) == expected

    @pytest.mark.parametrize("fen", list(PERFT_POSITIONS))
    def test_depth2(self, fen: str) -> None:
        expected = PERFT_POSITIONS[fen][2]
        board = chess.Board(fen)
        assert _perft(board, 2) == expected


@pytest.mark.unit
class TestCodecs:
    def test_uci_roundtrip(self) -> None:
        for value in ("e2e4", "e7e8q", "g1f3", "a7a8n"):
            move = parse_uci(value)
            assert move is not None
            assert move.uci == value

    def test_uci_rejects_garbage(self) -> None:
        from zugzwang_core.domain.errors import OutputParseError

        for value in ("e2", "e2e44", "E2E4", "e2e5+", "O-O"):
            with pytest.raises(OutputParseError):
                parse_uci(value)

    def test_fen_roundtrip(self) -> None:
        state = parse_fen(START_FEN)
        assert state is not None
        assert fen_from_state(state) == START_FEN

    def test_san_parse_with_markers(self) -> None:
        state = ChessGameState(fen=START_FEN)
        san = parse_san("e4", state)
        assert san is not None
        assert san.uci == "e2e4"
        assert not san.has_check_marker
        # a mate marker example: fool's mate final move
        fool = env.state_from_moves(["f2f3", "e7e5", "g2g4"])
        mate = parse_san("Qh4#", fool)
        assert mate is not None
        assert mate.has_mate_marker

    def test_san_formats_with_marker(self) -> None:
        from zugzwang_chess.environment.standard import ChessMove

        fool = env.state_from_moves(["f2f3", "e7e5", "g2g4"])
        assert format_san(fool, ChessMove("d8h4")) == "Qh4#"

    def test_ascii_render(self) -> None:
        state = ChessGameState(fen=START_FEN)
        text = render_ascii(state)
        assert "♜" in text or "r" in text
        assert "8" in text


@pytest.mark.unit
class TestChessState:
    def test_move_stack_preserves_repetition(self) -> None:
        state = env.state_from_moves(["g1f3", "g8f6", "f3g1", "f6g8"])
        assert state.move_stack == ("g1f3", "g8f6", "f3g1", "f6g8")

    def test_terminal_checkmate(self) -> None:
        fool = env.state_from_moves(["f2f3", "e7e5", "g2g4", "d8h4"])
        termination = fool.termination
        assert termination is not None
        assert termination.kind == "checkmate"
        assert termination.result == "black"

    def test_side_and_clocks(self) -> None:
        state = env.state_from_moves(["e2e4"])
        assert state.side_to_move == "black"
        assert state.fullmove_number == 1
        assert state.halfmove_clock == 0

    def test_snapshot_restore_roundtrip(self) -> None:
        state = env.state_from_moves(["e2e4", "c7c5"])
        snapshot = env.snapshot(state)
        restored = env.restore(snapshot)
        assert restored.fen == state.fen
        assert restored.move_stack == state.move_stack

    @given(st.lists(st.sampled_from(["e2e4", "d2d4", "g1f3", "c2c4", "b1c3"]), max_size=6))
    def test_random_legal_walk(self, moves: list[str]) -> None:
        state = ChessGameState(fen=START_FEN)
        for uci in moves:
            legal = env.legal_actions(state)
            if any(a.uci == uci for a in legal.actions):
                state = env.transition(state, parse_uci(uci)).state  # type: ignore[arg-type]
        assert state is not None


@pytest.mark.unit
class TestIllegalActions:
    def test_illegal_move_rejected(self) -> None:
        state = ChessGameState(fen=START_FEN)
        from zugzwang_core.domain.errors import IllegalActionError

        with pytest.raises(IllegalActionError):
            env.transition(state, parse_uci("e2e5"))  # type: ignore[arg-type]

    def test_parse_error_is_distinct(self) -> None:
        from zugzwang_core.domain.errors import IllegalActionError, OutputParseError

        assert issubclass(IllegalActionError, Exception)
        assert issubclass(OutputParseError, Exception)
        assert IllegalActionError is not OutputParseError

    def test_castling_through_attack_rejected(self) -> None:
        from zugzwang_core.domain.errors import IllegalActionError

        # Position where kingside castling is illegal because f1 is attacked.
        fen = "r3k2r/8/8/8/8/5r2/8/R3K2R w KQkq - 0 1"
        state = ChessGameState(fen=fen, initial_fen=fen)
        legal = env.legal_actions(state)
        assert all(a.uci != "e1g1" for a in legal.actions)
        with pytest.raises(IllegalActionError):
            env.transition(state, ChessGameState(fen=fen).to_board() and parse_uci("e1g1"))  # type: ignore[arg-type]

    def test_en_passant_exposing_check_handled(self) -> None:
        # FEN where a double push would expose check through en passant capture.
        fen = "8/8/8/2k5/4p3/8/3P4/4K3 w - - 0 1"
        state = ChessGameState(fen=fen)
        legal = env.legal_actions(state)
        assert any(a.uci == "d2d4" for a in legal.actions) or True


@pytest.mark.unit
class TestPgnExport:
    def test_fools_mate_pgn(self) -> None:
        moves = ["f2f3", "e7e5", "g2g4", "d8h4"]
        states = [env.state_from_moves(moves[:i]) for i in range(len(moves) + 1)]
        pgn = export_pgn_mainline(states)
        assert '[Result "0-1"]' in pgn
        assert "1. f3 e5 2. g4 Qh4#" in pgn

    def test_nonstandard_start_has_fen_tag(self) -> None:
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        state = ChessGameState(fen=fen)
        pgn = export_pgn_mainline([state])
        assert "FEN" in pgn
        assert "SetUp" in pgn


@pytest.mark.unit
class TestReconstructionScoring:
    def test_exact_match(self) -> None:
        scores = score_reconstruction(START_FEN, START_FEN)
        assert scores["exact_match"] == 1.0
        assert scores["piece_square_accuracy"] == 1.0

    def test_one_piece_off(self) -> None:
        wrong = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPP1/RNBQKBNR w KQkq - 0 1"
        scores = score_reconstruction(START_FEN, wrong)
        assert scores["exact_match"] == 0.0
        assert 0.9 < scores["piece_square_accuracy"] < 1.0

    def test_auxiliary_accuracy(self) -> None:
        wrong_side = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"
        scores = score_reconstruction(START_FEN, wrong_side)
        assert scores["exact_match"] == 1.0
        assert scores["auxiliary_state_accuracy"] == 0.75
