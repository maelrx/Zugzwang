"""ZGW-0073: multimodal observation — renderer determinism, conflict manifest,
ImagePart contract, adapter lowering and capability preflight."""

from __future__ import annotations

import base64
import hashlib

from zugzwang_chess.codecs.board_png import BoardRenderSpec, render_board_png
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
from zugzwang_chess.strategies._image import (
    build_message_parts,
    image_conflict_manifest,
    image_part_from_observation,
)
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.ports.environment import ObservationPolicy
from zugzwang_core.ports.model import Capability, ImagePart

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _fen_after(fen: str, uci: str) -> str:
    state = ChessGameState(fen=fen)
    from chess import Move

    board = state.to_board()
    board.push(Move.from_uci(uci))
    return board.fen()


class TestRendererDeterminism:
    def test_same_fen_same_spec_byte_identical(self) -> None:
        a = render_board_png(START_FEN)
        b = render_board_png(START_FEN)
        assert a.bytes == b.bytes
        assert a.content_sha256 == b.content_sha256

    def test_sha256_matches_bytes(self) -> None:
        rendered = render_board_png(START_FEN)
        assert rendered.content_sha256 == hashlib.sha256(rendered.bytes).hexdigest()

    def test_orientation_changes_bytes(self) -> None:
        a = render_board_png(START_FEN)
        b = render_board_png(START_FEN, BoardRenderSpec(orientation="black"))
        assert a.bytes != b.bytes
        assert a.metadata["orientation"] == "white"
        assert b.metadata["orientation"] == "black"

    def test_coordinates_change_bytes(self) -> None:
        a = render_board_png(START_FEN)
        b = render_board_png(START_FEN, BoardRenderSpec(coordinates=False))
        assert a.bytes != b.bytes
        assert a.metadata["coordinates"] is True
        assert b.metadata["coordinates"] is False

    def test_state_hash_differs_between_positions(self) -> None:
        a = render_board_png(START_FEN)
        b = render_board_png(_fen_after(START_FEN, "e2e4"))
        assert a.metadata["source_state_hash"] != b.metadata["source_state_hash"]

    def test_renderer_metadata_complete(self) -> None:
        rendered = render_board_png(START_FEN)
        for key in (
            "renderer_id",
            "renderer_version",
            "theme",
            "orientation",
            "coordinates",
            "square_size_px",
            "width",
            "height",
            "font_sha256",
            "source_state_hash",
            "source_fen_board",
        ):
            assert key in rendered.metadata, key


class TestImageObservation:
    def test_image_payload_present_with_metadata(self) -> None:
        env = StandardChessEnvironment()
        policy = ObservationPolicy(settings={"position": {"fen": True}, "image": {"enabled": True}})
        observation = env.observe(ChessGameState(fen=START_FEN), policy)
        image = observation["image"]
        assert isinstance(image, dict)
        assert image["mime"] == "image/png"
        assert image["content_sha256"]
        assert isinstance(image["renderer"], dict)
        assert image["renderer"]["source_state_hash"]

    def test_no_image_when_disabled(self) -> None:
        env = StandardChessEnvironment()
        policy = ObservationPolicy(settings={"position": {"fen": True}})
        observation = env.observe(ChessGameState(fen=START_FEN), policy)
        assert "image" not in observation

    def test_conflict_manifest_on_fen_override(self) -> None:
        env = StandardChessEnvironment()
        policy = ObservationPolicy(
            settings={
                "position": {"fen": True},
                "image": {"enabled": True, "fen_override": _fen_after(START_FEN, "e2e4")},
            }
        )
        observation = env.observe(ChessGameState(fen=START_FEN), policy)
        conflict = observation["image_conflict"]
        assert conflict["source_state_fen"].startswith(START_FEN.split(" ")[0])
        assert conflict["image_fen"].startswith(_fen_after(START_FEN, "e2e4").split(" ")[0])
        assert any("e2" in square for square in conflict["delta_squares"])
        assert image_conflict_manifest(observation) is not None

    def test_no_conflict_manifest_when_consistent(self) -> None:
        env = StandardChessEnvironment()
        policy = ObservationPolicy(settings={"position": {"fen": True}, "image": {"enabled": True}})
        observation = env.observe(ChessGameState(fen=START_FEN), policy)
        assert "image_conflict" not in observation
        assert image_conflict_manifest(observation) is None

    def test_modality_authority_recorded(self) -> None:
        env = StandardChessEnvironment()
        policy = ObservationPolicy(
            settings={
                "position": {"fen": True},
                "image": {"enabled": True},
                "modality_authority": "text",
            }
        )
        observation = env.observe(ChessGameState(fen=START_FEN), policy)
        assert observation["modality_authority"] == "text"


class TestImagePartContract:
    def test_roundtrip_and_data_url(self) -> None:
        rendered = render_board_png(START_FEN)
        part = ImagePart(
            mime="image/png",
            width=rendered.width,
            height=rendered.height,
            content_sha256=rendered.content_sha256,
            data_base64=base64.b64encode(rendered.bytes).decode("ascii"),
            renderer=rendered.metadata,
        )
        assert part.data_url().startswith("data:image/png;base64,")
        assert base64.b64decode(part.data_base64) == rendered.bytes

    def test_helper_builds_part_and_requires_capability(self) -> None:
        rendered = render_board_png(START_FEN)
        observation: dict[str, JsonValue] = {
            "image": {
                "mime": "image/png",
                "width": rendered.width,
                "height": rendered.height,
                "content_sha256": rendered.content_sha256,
                "data_base64": rendered.base64(),
                "renderer": rendered.metadata,
            }
        }
        part = image_part_from_observation(observation)
        assert isinstance(part, ImagePart)
        parts, required = build_message_parts(observation, "prompt")
        assert len(parts) == 2
        assert Capability.MULTIMODAL_IMAGE in required

    def test_helper_returns_none_without_image(self) -> None:
        assert image_part_from_observation({}) is None
        parts, required = build_message_parts({}, "prompt")
        assert len(parts) == 1
        assert not required

    def test_mime_fallback_to_png(self) -> None:
        rendered = render_board_png(START_FEN)
        observation: dict[str, JsonValue] = {
            "image": {
                "mime": "image/avif",
                "width": rendered.width,
                "height": rendered.height,
                "content_sha256": rendered.content_sha256,
                "data_base64": rendered.base64(),
                "renderer": rendered.metadata,
            }
        }
        part = image_part_from_observation(observation)
        assert part is not None
        assert part.mime == "image/png"


class TestConflictTransform:
    def test_displaces_exactly_one_piece(self) -> None:
        from zugzwang_chess.codecs.board_png import piece_symbols
        from zugzwang_chess.codecs.conflict import displace_one_minor_piece

        for fen in (
            "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
            "8/8/5k2/1R3p2/5P2/3r4/8/6K1 w - - 0 52",
            "8/5k2/4p3/4P1p1/3p2Pp/3K3P/8/8 w - - 0 41",
        ):
            displaced = displace_one_minor_piece(fen)
            a = piece_symbols(fen)
            b = piece_symbols(displaced)
            changed = [sq for sq in sorted(set(a) | set(b)) if a.get(sq, ".") != b.get(sq, ".")]
            assert len(changed) == 2, (fen, changed)

    def test_conflict_observation_has_manifest(self) -> None:
        from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment
        from zugzwang_core.ports.environment import ObservationPolicy

        env = StandardChessEnvironment()
        state = ChessGameState(
            fen="rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6"
        )
        policy = ObservationPolicy(
            settings={
                "position": {"fen": True},
                "image": {"enabled": True, "fen_override": "__conflict_auto__"},
                "modality_authority": "text",
            }
        )
        observation = env.observe(state, policy)
        conflict = observation["image_conflict"]
        assert (
            conflict["source_state_fen"].split(" ")[0]
            == "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R"
        )
        assert conflict["delta_squares"]
