from __future__ import annotations

import random
import time
from typing import Any

from zugzwang.core.board import BoardManager
from zugzwang.core.models import GameRecord, MoveRecord
from zugzwang.core.players import PlayerInterface
from zugzwang.infra.ids import timestamp_utc


def play_game(
    experiment_id: str,
    game_number: int,
    config_hash: str,
    seed: int,
    players_cfg: dict[str, Any],
    white_player: PlayerInterface,
    black_player: PlayerInterface,
    max_plies: int,
) -> GameRecord:
    board = BoardManager()
    rng = random.Random(seed)
    history_uci: list[str] = []
    move_records: list[MoveRecord] = []

    started = time.perf_counter()
    termination = "max_moves"

    for _ in range(max_plies):
        state = board.game_state(history_uci)
        if state.is_terminal:
            termination = state.termination_reason or "draw_rule"
            break

        actor = white_player if state.active_color == "white" else black_player
        decision = actor.choose_move(state)

        apply_result = board.apply_move(decision.move_uci)
        if not apply_result.ok:
            # Invariant: never apply illegal move. Use legal fallback if needed.
            fallback_move = rng.choice(state.legal_moves_uci)
            decision.move_uci = fallback_move
            decision.is_legal = True
            decision.parse_ok = False
            decision.error = decision.error or apply_result.error or "illegal_move_fallback"
            apply_result = board.apply_move(fallback_move)

        decision.move_san = apply_result.san
        history_uci.append(decision.move_uci)
        move_records.append(
            MoveRecord(
                ply_number=len(history_uci),
                color=state.active_color,
                fen_before=state.fen,
                move_decision=decision,
            )
        )

    if board.is_terminal():
        termination = board.termination_reason() or termination

    duration = time.perf_counter() - started
    token_usage = {
        "input": sum(record.move_decision.tokens_input for record in move_records),
        "output": sum(record.move_decision.tokens_output for record in move_records),
    }
    total_cost = float(sum(record.move_decision.cost_usd for record in move_records))

    return GameRecord(
        experiment_id=experiment_id,
        game_number=game_number,
        config_hash=config_hash,
        seed=seed,
        players=players_cfg,
        moves=move_records,
        result=board.result(),
        termination=termination,
        token_usage=token_usage,
        cost_usd=total_cost,
        duration_seconds=duration,
        timestamp_utc=timestamp_utc(),
    )
