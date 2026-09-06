"""CB-WO-03 acceptance — TEST-005..017 applicable subset (PRD §36, §38.4).

Pure, offline, deterministic: no evaluator, no ranking, no pruning. TEST-001
to TEST-004 and TEST-018 (snapshot/history/anchor with persistence) belong to
CB-WO-04/05 and are intentionally absent here.
"""

import chess
import pytest

from zugzwang_chess.cognition import (
    ActionStateMismatch,
    ChessPerception,
    PositionPacket,
    compute_delta,
    reconstruct,
    require_action_belongs,
)
from zugzwang_chess.environment.standard import ChessGameState, StandardChessEnvironment

pytestmark = pytest.mark.unit

POLICY_HASH = "a" * 64
NODE = "node-test-root"


def _perception(page_size: int = 32) -> ChessPerception:
    return ChessPerception(
        environment=StandardChessEnvironment(),
        rules_version="standard/v1",
        policy_hash=POLICY_HASH,
        page_size=page_size,
    )


START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _state(fen: str) -> ChessGameState:
    """State anchored at the position itself (no recorded history)."""
    return ChessGameState(fen=fen, initial_fen=fen, move_stack=())


def test_packet_is_deterministic_and_telemetry_free() -> None:
    state = _state(START)
    p1 = _perception().build_packet(state, NODE)
    p2 = _perception().build_packet(state, NODE)
    assert p1.content_hash() == p2.content_hash()
    assert p1.terminal.claim_policy is None  # TEST-015: claims are not automatic


def test_pagination_recomposes_exactly_the_kernel_set() -> None:
    """TEST-005: paginar e recompor exatamente o conjunto do kernel."""
    state = _state(START)
    perception = _perception(page_size=8)
    full = perception.build_packet(state, NODE)
    assert full.legal_actions.total_count == 20

    gathered: list[str] = []
    cursor: int | None = 0
    while cursor is not None:
        page = perception.build_packet(state, NODE, cursor=cursor)
        gathered.extend(item.uci for item in page.legal_actions.items)
        cursor = page.legal_actions.next_cursor
    env = StandardChessEnvironment()
    kernel = sorted(m.uci for m in env.legal_actions(state).actions)
    assert sorted(gathered) == kernel
    assert not full.legal_actions.complete  # three pages; no single complete page


def test_action_id_from_another_state_is_rejected() -> None:
    """TEST-006: action key de outro estado → ACTION_STATE_MISMATCH."""
    state = _state(START)
    packet = _perception().build_packet(state, NODE)
    other_state = _state("rnbqkbnr/pppppppp/8/8/4P3/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1")
    other_packet = _perception().build_packet(other_state, NODE)
    foreign = packet.legal_actions.items[0]
    with pytest.raises(ActionStateMismatch):
        require_action_belongs(other_packet.state.state_key, foreign, "uci/v1", POLICY_HASH)


def test_absolute_pin_is_formal_and_geometric_attack_is_not_capture() -> None:
    """TEST-008/009: cravada absoluta formal; ataque geométrico ≠ captura legal."""
    pinned_fen = "4k3/8/8/1b6/8/3N4/4K3/8 w - - 0 1"
    packet = _perception().build_packet(_state(pinned_fen), NODE)
    pins = [r for r in packet.relations.items if r.get("kind") == "absolute_pin"]
    assert pins and pins[0]["piece_square"] == "d3" and pins[0]["pinner_square"] == "b5"
    assert pins[0]["king_square"] == "e2"

    # Relative pin surface: the substrate attack map still lists squares even
    # though the pinned knight has no legal moves along the diagonal.
    board = chess.Board(pinned_fen)
    assert board.attacks(chess.parse_square("d3"))  # geometric, not legality
    legal_uci = {item.uci for item in packet.legal_actions.items}
    assert not any(uci.startswith("d3") for uci in legal_uci)  # knight cannot move


def test_no_hidden_assistance_in_cognition_sources() -> None:
    """TEST-010: o extrator não chama evaluator, não rankeia nem poda ações.

    Scans the actual AST (imports and calls), not comments or docstrings.
    """
    import ast
    import inspect

    from zugzwang_chess.cognition import delta, perception, relations

    forbidden_modules = ("evaluator", "stockfish", "engine")
    forbidden_calls = {"score", "evaluate", "evaluate_position", "analyse", "analyze", "rank"}
    for module in (perception, relations, delta):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(f in alias.name.lower() for f in forbidden_modules), alias.name
            elif isinstance(node, ast.ImportFrom):
                module_name = (node.module or "").lower()
                assert not any(f in module_name for f in forbidden_modules), node.module
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr.lower() not in forbidden_calls, node.func.attr
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id.lower() not in forbidden_calls, node.func.id


def test_castling_follows_the_rules_kernel() -> None:
    """TEST-011: roque permitido e bloqueado pelo contrato das regras."""
    free = _perception().build_packet(
        _state("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"), NODE
    )
    legal_uci = {item.uci for item in free.legal_actions.items}
    assert {"e1g1", "e1c1"}.issubset(legal_uci)

    blocked = _perception().build_packet(_state("4k3/8/8/8/8/5q2/8/R3K2R w KQ - 0 1"), NODE)
    blocked_uci = {item.uci for item in blocked.legal_actions.items}
    assert "e1g1" not in blocked_uci
    assert "e1c1" not in blocked_uci


def test_en_passant_including_king_line_opening() -> None:
    """TEST-012: captura en passant e abertura de linha para o próprio rei."""
    available = _perception().build_packet(
        _state("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"), NODE
    )
    assert "e5f6" in {item.uci for item in available.legal_actions.items}

    # exd3 would expose the a4 king to Qh4 along rank 4 — not legal at all.
    pinned_ep = _perception().build_packet(_state("8/8/8/8/k2Pp2Q/8/8/4K3 b - d3 0 1"), NODE)
    assert "e4d3" not in {item.uci for item in pinned_ep.legal_actions.items}


def test_promotions_preserved_with_distinct_ids() -> None:
    """TEST-013: todas as promoções legais preservadas com IDs distintos."""
    packet = _perception().build_packet(_state("8/P6k/8/8/8/8/8/K7 w - - 0 1"), NODE)
    promotions = [item for item in packet.legal_actions.items if item.uci == "a7a8q"]
    all_promo_ids = [
        item.action_id for item in packet.legal_actions.items if item.uci.startswith("a7a8")
    ]
    assert len(promotions) == 1
    assert len(all_promo_ids) == 4
    assert len(set(all_promo_ids)) == 4


def test_terminal_node_sets_automatic_termination() -> None:
    """TEST-014: término automático — nó terminal não permite nova expansão."""
    mate = _perception().build_packet(
        _state("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"), NODE
    )
    assert mate.terminal.automatic is True
    assert mate.terminal.kind == "checkmate"
    assert mate.legal_actions.total_count == 0


def test_claim_is_never_automatic_termination() -> None:
    """TEST-015: claim disponível não vira término automático sem política."""
    claimable = _perception().build_packet(
        _state("rnbqkbnr/ppp1pppp/8/3p4/8/8/PPPPPPPP/RNBQKBNR w KQkq d6 99 2"), NODE
    )
    assert claimable.terminal.automatic is False
    assert claimable.terminal.claim_policy is None


def _adjacent_packets(fen_before: str, uci: str) -> tuple[PositionPacket, PositionPacket, str]:
    env = StandardChessEnvironment()
    state = _state(fen_before)
    action = next(m for m in env.legal_actions(state).actions if m.uci == uci)
    after = env.transition(state, action).state
    perception = _perception()
    return (
        perception.build_packet(state, NODE),
        perception.build_packet(after, NODE),
        action.uci,
    )


def test_adjacent_delta_reconstructs_target_projection() -> None:
    """TEST-016: aplicar delta à projeção-origem obtém a projeção-alvo."""
    origin, target, uci = _adjacent_packets(START, "e2e4")
    action_id = next(item.action_id for item in origin.legal_actions.items if item.uci == uci)
    delta = compute_delta(
        origin, target, responsible_action_id=action_id, responsible_action_uci=uci
    )
    assert delta.comparison_kind == "adjacent"
    assert delta.side_changed is True
    reconstructed = reconstruct(origin, delta)
    assert reconstructed == target.representation.piece_map


def test_castling_delta_moves_king_and_rook() -> None:
    origin, target, uci = _adjacent_packets(
        "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1", "e1g1"
    )
    action_id = next(item.action_id for item in origin.legal_actions.items if item.uci == uci)
    delta = compute_delta(
        origin, target, responsible_action_id=action_id, responsible_action_uci=uci
    )
    moved_from = {c.from_square for c in delta.moved if c.from_square}
    assert {"e1", "h1"}.issubset(moved_from)
    assert delta.castling_rights_changed is True
    assert reconstruct(origin, delta) == target.representation.piece_map


def test_arbitrary_delta_never_blames_a_single_action() -> None:
    """TEST-017: comparação arbitrária não atribui diferença a uma ação."""
    origin, target, _ = _adjacent_packets(START, "e2e4")
    with pytest.raises(ValueError):
        compute_delta(origin, target, responsible_action_id="some-action")
    delta = compute_delta(origin, target)
    assert delta.comparison_kind == "arbitrary"
    assert delta.responsible_action_id is None


def test_promotion_delta_records_promotion() -> None:
    origin, target, uci = _adjacent_packets("8/P6k/8/8/8/8/8/K7 w - - 0 1", "a7a8q")
    action_id = next(item.action_id for item in origin.legal_actions.items if item.uci == uci)
    delta = compute_delta(
        origin, target, responsible_action_id=action_id, responsible_action_uci=uci
    )
    assert delta.promoted and delta.promoted[0].from_square == "a7"
    assert delta.promoted[0].piece == "Q"
    assert reconstruct(origin, delta) == target.representation.piece_map
