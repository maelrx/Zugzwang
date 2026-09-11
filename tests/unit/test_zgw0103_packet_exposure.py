"""ZGW-0103 R3 — declared ascii/history exposure actually ships in the packet.

Dossier §5.1: the arena's `position: {ascii: true}` and history-window
declarations never reached the model through the L0 packet. Here the policy
declared in the manifest observation block must be observable in the packet —
or rejected as invalid configuration.
"""

import pytest

from zugzwang_chess.cognition import (
    ChessPerception,
    CognitionError,
    PacketExposure,
)
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment

pytestmark = pytest.mark.unit

POLICY_HASH = "a" * 64
NODE = "node-test-root"
START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_E4_D5 = "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2"


def _perception(exposure: PacketExposure | None = None) -> ChessPerception:
    return ChessPerception(
        environment=StandardChessEnvironment(),
        rules_version="standard/v1",
        policy_hash=POLICY_HASH,
        exposure=exposure,
    )


def _state(fen: str, moves: tuple[str, ...] = ()) -> ChessGameState:
    return ChessGameState(fen=fen, initial_fen=START, move_stack=moves)


def test_default_exposure_stays_fen_and_piece_map_only() -> None:
    packet = _perception().build_packet(_state(START), NODE)
    assert packet.representation.fen == START
    assert packet.representation.ascii is None
    assert packet.history == ()


def test_declared_ascii_is_serialized_into_the_packet() -> None:
    exposure = PacketExposure(ascii=True)
    packet = _perception(exposure).build_packet(_state(START), NODE)
    assert packet.representation.ascii is not None
    assert "♖" in packet.representation.ascii  # a rendered board has pieces
    # the ascii ablation changes the observable content hash (dossier §5.3)
    plain = _perception().build_packet(_state(START), NODE)
    assert packet.content_hash() != plain.content_hash()


def test_declared_history_window_ships_with_ply_indices() -> None:
    moves = ("e2e4", "d7d5")
    exposure = PacketExposure(history_mode="last_n", history_plies=6, history_notation="uci")
    packet = _perception(exposure).build_packet(_state(AFTER_E4_D5, moves), NODE)
    assert [item.uci for item in packet.history] == list(moves)
    assert [item.ply_index for item in packet.history] == [0, 1]
    assert all(item.san is None for item in packet.history)


def test_history_full_and_san_notation() -> None:
    moves = ("e2e4", "d7d5")
    exposure = PacketExposure(history_mode="full", history_notation="san")
    packet = _perception(exposure).build_packet(_state(AFTER_E4_D5, moves), NODE)
    assert [item.san for item in packet.history] == ["e4", "d5"]


def test_from_observation_maps_the_manifest_policy() -> None:
    exposure = PacketExposure.from_observation(
        {
            "position": {"fen": True, "ascii": True},
            "history": {"mode": "last_n", "plies": 6, "notation": "uci"},
        }
    )
    assert exposure.fen is True
    assert exposure.ascii is True
    assert exposure.history_mode == "last_n"
    assert exposure.history_plies == 6
    assert exposure.history_notation == "uci"


def test_from_observation_rejects_unusable_history_declarations() -> None:
    with pytest.raises(CognitionError):
        PacketExposure.from_observation({"history": {"mode": "last_n"}})  # no plies
    with pytest.raises(CognitionError):
        PacketExposure.from_observation(
            {"history": {"mode": "last_n", "plies": 4, "notation": "x"}}
        )
    with pytest.raises(CognitionError):
        PacketExposure.from_observation({"history": {"mode": "wormhole"}})


def test_history_never_fabricates_moves_without_a_stack() -> None:
    exposure = PacketExposure(history_mode="full")
    packet = _perception(exposure).build_packet(_state(START), NODE)
    assert packet.history == ()


@pytest.mark.parametrize("notation", ["uci", "san"])
@pytest.mark.parametrize("window", [1, 2, 3, 24])
def test_truncated_history_replays_prefix_before_window(notation: str, window: int) -> None:
    # Actual sequence that crashed the arena at ply 25 with a 24-ply window.
    moves = [
        "d2d4",
        "g8f6",
        "c2c4",
        "e7e6",
        "g1f3",
        "f8b4",
        "b1c3",
        "e8g8",
        "a2a3",
        "b4c3",
        "b2c3",
        "d7d5",
        "c1g5",
        "h7h6",
        "g5f4",
        "f6h5",
        "f4h6",
        "g7h6",
        "f3e5",
        "f7f6",
        "e5g6",
        "f8f7",
        "e2e3",
        "g8g7",
        "d1h5",
    ]
    state = StandardChessEnvironment().state_from_moves(moves)
    before = state.to_board().fen()
    full = _perception(PacketExposure(history_mode="full", history_notation=notation)).build_packet(
        state, NODE
    )
    limited = _perception(
        PacketExposure(history_mode="last_n", history_plies=window, history_notation=notation)
    ).build_packet(state, NODE)
    assert limited.history == full.history[-window:]
    assert state.to_board().fen() == before
    assert limited.history[-1].uci == "d1h5"
    assert limited.history[-1].san == ("Qxh5" if notation == "san" else None)


@pytest.mark.parametrize("notation", ["uci", "san"])
def test_truncated_history_uses_custom_initial_position(notation: str) -> None:
    state = StandardChessEnvironment().state_from_moves(
        ["a7a8q", "g6h5", "a8h8"], start_fen="8/P7/6k1/8/8/8/8/6K1 w - - 0 1"
    )
    packet = _perception(
        PacketExposure(history_mode="last_n", history_plies=1, history_notation=notation)
    ).build_packet(state, NODE)
    assert [(item.ply_index, item.uci, item.san) for item in packet.history] == [
        (2, "a8h8", "Qh8+" if notation == "san" else None)
    ]
