"""PositionDelta (PRD §8.6): compare two projections without interpretation.

An adjacent delta carries the responsible action and must reconstruct the
target projection from the origin plus the delta (TEST-016). An arbitrary
comparison never attributes differences to a single action (TEST-017). The
delta does not apply real moves and never invents purpose: "the rook left the
file" is formal; "it abandoned the attack" is interpretation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .packet import PositionPacket


class PieceChange(BaseModel):
    """One piece-level change between two projections.

    ``piece`` is the symbol placed at ``to_square`` (or removed from
    ``from_square``); ``previous_piece`` records what it replaced, if any.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    piece: str = Field(min_length=1)
    from_square: str | None = None
    to_square: str | None = None
    previous_piece: str | None = None


class PositionDelta(BaseModel):
    """Formal diff between two authorized projections (§8.6)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_kind: Literal["adjacent", "arbitrary"]
    origin_state_key: str
    target_state_key: str
    moved: tuple[PieceChange, ...] = ()
    promoted: tuple[PieceChange, ...] = ()
    removed: tuple[PieceChange, ...] = ()
    replaced: tuple[PieceChange, ...] = ()
    side_changed: bool = False
    castling_rights_changed: bool = False
    halfmove_clock_from: int = 0
    halfmove_clock_to: int = 0
    fullmove_from: int = 0
    fullmove_to: int = 0
    responsible_action_id: str | None = None


def _fen_parts(packet: PositionPacket) -> list[str]:
    if packet.representation.fen is None:
        raise ValueError("delta requires packets with fen representation")
    return packet.representation.fen.split(" ")


def _piece_map(packet: PositionPacket) -> dict[str, str]:
    if packet.representation.piece_map is None:
        raise ValueError("delta requires packets with piece_map representation")
    return packet.representation.piece_map


def _removed_added(
    origin_map: dict[str, str], target_map: dict[str, str]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    disappeared = sorted((s, p) for s, p in origin_map.items() if s not in target_map)
    added = sorted((s, p) for s, p in target_map.items() if s not in origin_map)
    return disappeared, added


def _pair_moved(
    disappeared: list[tuple[str, str]], added: list[tuple[str, str]]
) -> tuple[list[PieceChange], list[tuple[str, str]], list[tuple[str, str]]]:
    """Pair same-symbol disappearance/appearance as moves (e.g. castling rook)."""
    moved: list[PieceChange] = []
    left_out = list(disappeared)
    left_in = list(added)
    for to_sq, piece in added:
        for from_sq, src_piece in left_out:
            if from_sq == to_sq:
                continue
            if src_piece == piece:
                moved.append(PieceChange(piece=piece, from_square=from_sq, to_square=to_sq))
                left_out.remove((from_sq, src_piece))
                left_in.remove((to_sq, piece))
                break
    return moved, left_out, left_in


def compute_delta(
    origin: PositionPacket,
    target: PositionPacket,
    responsible_action_id: str | None = None,
    responsible_action_uci: str | None = None,
) -> PositionDelta:
    """Compute the formal diff between two packets (§8.6).

    Adjacent when a responsible action is given (both id and uci); arbitrary
    otherwise. The origin and target must carry fen and piece_map.
    """
    origin_parts = _fen_parts(origin)
    target_parts = _fen_parts(target)
    origin_map = _piece_map(origin)
    target_map = _piece_map(target)

    moved: list[PieceChange] = []
    promoted: list[PieceChange] = []
    removed: list[PieceChange] = []
    replaced: list[PieceChange] = []

    if responsible_action_id is not None:
        if responsible_action_uci is None:
            raise ValueError("adjacent delta requires the responsible action uci")
        if len(responsible_action_uci) not in (4, 5):
            raise ValueError(f"invalid uci {responsible_action_uci!r}")
        from_sq, to_sq = responsible_action_uci[:2], responsible_action_uci[2:4]
        is_promotion = len(responsible_action_uci) == 5

        disappeared, added = _removed_added(origin_map, target_map)
        replaced_squares = [
            s for s in sorted(set(origin_map) & set(target_map)) if origin_map[s] != target_map[s]
        ]
        # The mover leaves from_sq (disappeared or replaced there).
        if from_sq not in origin_map:
            raise ValueError("responsible action from_square has no piece in origin")
        mover_piece = origin_map[from_sq]
        if to_sq in origin_map and to_sq != from_sq:
            removed.append(PieceChange(piece=origin_map[to_sq], from_square=to_sq))
        if is_promotion:
            promoted.append(
                PieceChange(
                    piece=target_map[to_sq],
                    from_square=from_sq,
                    to_square=to_sq,
                    previous_piece=mover_piece,
                )
            )
        else:
            moved.append(
                PieceChange(
                    piece=target_map.get(to_sq, mover_piece), from_square=from_sq, to_square=to_sq
                )
            )
        leftovers = [d for d in disappeared if d[0] not in {from_sq, to_sq}]
        moved_rest, left_out, left_in = _pair_moved(leftovers, [a for a in added if a[0] != to_sq])
        moved.extend(moved_rest)
        for sq, piece in left_out:
            if sq == to_sq:
                continue  # captured piece already recorded
            removed.append(PieceChange(piece=piece, from_square=sq))
        for sq in replaced_squares:
            replaced.append(
                PieceChange(
                    piece=target_map[sq],
                    from_square=sq,
                    to_square=sq,
                    previous_piece=origin_map[sq],
                )
            )
        if left_out and all(d[0] == to_sq for d in left_out):
            for sq, piece in left_out:
                if sq == to_sq:
                    removed.append(PieceChange(piece=piece, from_square=sq))
            left_out = [d for d in left_out if d[0] != to_sq]
        if left_out or left_in:
            raise ValueError("adjacent delta could not explain all piece changes")
    else:
        disappeared, added = _removed_added(origin_map, target_map)
        for sq, piece in disappeared:
            removed.append(PieceChange(piece=piece, from_square=sq))
        for sq, piece in added:
            moved.append(PieceChange(piece=piece, to_square=sq))
        replaced_squares = [
            s for s in sorted(set(origin_map) & set(target_map)) if origin_map[s] != target_map[s]
        ]
        for sq in replaced_squares:
            replaced.append(
                PieceChange(
                    piece=target_map[sq],
                    from_square=sq,
                    to_square=sq,
                    previous_piece=origin_map[sq],
                )
            )

    return PositionDelta(
        comparison_kind="adjacent" if responsible_action_id is not None else "arbitrary",
        origin_state_key=origin.state.state_key,
        target_state_key=target.state.state_key,
        moved=tuple(moved),
        promoted=tuple(promoted),
        removed=tuple(removed),
        replaced=tuple(replaced),
        side_changed=origin_parts[1] != target_parts[1],
        castling_rights_changed=origin_parts[2] != target_parts[2],
        halfmove_clock_from=int(origin_parts[4]),
        halfmove_clock_to=int(target_parts[4]),
        fullmove_from=int(origin_parts[5]),
        fullmove_to=int(target_parts[5]),
        responsible_action_id=responsible_action_id,
    )


def reconstruct(origin: PositionPacket, delta: PositionDelta) -> dict[str, str]:
    """Apply the delta to the origin projection (TEST-016).

    Returns the reconstructed piece map. The integral snapshot remains the
    authority for replay; reconstruction covers the projection only.
    """
    if delta.comparison_kind != "adjacent":
        raise ValueError("only adjacent deltas reconstruct a target projection")
    board_map = dict(_piece_map(origin))
    for change in delta.moved + delta.promoted:
        if change.from_square is None or change.to_square is None:
            raise ValueError("moved/promoted change requires from and to squares")
        board_map.pop(change.from_square, None)
        board_map[change.to_square] = change.piece
    for change in delta.removed:
        if change.from_square is None:
            raise ValueError("removed change requires from_square")
        board_map.pop(change.from_square, None)
    for change in delta.replaced:
        if change.from_square is None:
            raise ValueError("replaced change requires from_square")
        board_map[change.from_square] = change.piece
    return dict(sorted(board_map.items()))
