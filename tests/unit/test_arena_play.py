"""ZGW-0108 arena play mode: offline unit tests (scripted fake backend)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from zugzwang_chess.cognition.packet import PositionPacket, require_action_belongs
from zugzwang_cli.arena.game import ArenaGame, load_game, new_game_id
from zugzwang_cli.arena.loop import ROOT_NODE_ID, ArenaDecisionLoop
from zugzwang_cli.arena.positions import ARENA_POLICY_HASH, BoardFacade
from zugzwang_core.domain.errors import ProviderTimeoutError
from zugzwang_core.domain.money import TokenUsage, UsageSource
from zugzwang_core.ports.model import (
    CallContext,
    MessageRole,
    ModelRef,
    NormalizedResponse,
    ProviderResult,
    StopReason,
    TextPart,
    ToolCallPart,
    WireFidelity,
)


def json_payload(content: str) -> dict[str, Any]:
    import json

    return dict(json.loads(content))


MODEL_REF = ModelRef(
    backend="provider.antigravity_cli", provider="antigravity-cli", model="gemini-3.8-flash-low"
)


def _tool_call(tool: str, arguments: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(tool_call_id=f"call_{tool}", tool_name=tool, arguments=arguments)


def _provider_result(
    request: Any, tool_calls: tuple[ToolCallPart, ...], text: str = ""
) -> ProviderResult:
    now = datetime.now(UTC)
    normalized = NormalizedResponse(
        content_parts=(TextPart(text=text),),
        tool_calls=tool_calls,
        stop_reason=StopReason(canonical="end_turn"),
        model_requested=request.model,
        model_reported=request.model.model,
        request_id="fake-req",
        usage=TokenUsage(input_tokens=10, output_tokens=5, source=UsageSource.PROVIDER),
        started_at=now,
        finished_at=now,
        adapter_version="test",
        wire_fidelity=WireFidelity.FULL,
        warnings=(),
    )
    return ProviderResult(
        response=normalized, wire_request={}, wire_response={}, wire_fidelity=WireFidelity.FULL
    )


class ScriptedBackend:
    """Replays scripted tool-call turns; raises scripted exceptions."""

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.requests: list[Any] = []

    async def infer(self, request: Any, context: CallContext) -> ProviderResult:
        self.requests.append(request)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return _provider_result(request, tuple(item))

    async def close(self) -> None:
        return None


def _run(loop: ArenaDecisionLoop) -> Any:
    return asyncio.run(loop.run())


def test_board_facade_legal_set_and_action_ids() -> None:
    board = BoardFacade()
    entries = board.legal_entries(board.state)
    assert len(entries) == 20
    packet: PositionPacket = board.packet(board.state, ROOT_NODE_ID)
    assert packet.state.node_id == ROOT_NODE_ID
    assert packet.legal_actions.total_count == 20
    for item in packet.legal_actions.items:
        require_action_belongs(packet.state.state_key, item, "uci/v1", ARENA_POLICY_HASH)
    assert board.resolve_action(board.state, entries[0][1]) == entries[0][0]
    assert board.resolve_action(board.state, "e2e4") == "e2e4"
    assert board.resolve_action(board.state, "e2e9") is None
    dests, promotable = board.dests()
    assert dests["e2"] == ["e3", "e4"]
    assert promotable == []


def test_loop_commits_legal_finalize_from_uci() -> None:
    board = BoardFacade()
    backend = ScriptedBackend(
        [
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "e2e4"})],
        ]
    )
    outcome = _run(
        ArenaDecisionLoop(
            game_id="g1", board=board, backend=backend, model_ref=MODEL_REF, max_rounds=4
        )
    )
    assert outcome.status == "COMMITTED"
    assert outcome.uci == "e2e4"
    assert outcome.rounds_used == 1
    # The loop is a pure decision engine: committing to the game board is
    # record_model_outcome's job (same split as coordinator/strategy runs).
    assert board.turn == "white"
    assert len(board.moves) == 0


def test_loop_recovers_from_illegal_finalize() -> None:
    board = BoardFacade()
    backend = ScriptedBackend(
        [
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "e2e9"})],
            [
                _tool_call(
                    "board_expand", {"node_id": ROOT_NODE_ID, "action_ids": ["x"] * 0 + ["nope"]}
                )
            ],
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "d2d4"})],
        ]
    )
    outcome = _run(
        ArenaDecisionLoop(
            game_id="g2", board=board, backend=backend, model_ref=MODEL_REF, max_rounds=4
        )
    )
    assert outcome.status == "COMMITTED"
    assert outcome.uci == "d2d4"
    assert outcome.protocol_errors == 2
    # The transcript exposed the errors back to the model: rounds 2 and 3 carry
    # is_error tool results after the failed finalize/expand.
    third_request = backend.requests[2]
    tool_messages = [m for m in third_request.messages if m.role is MessageRole.TOOL]
    assert any(part.is_error for m in tool_messages for part in m.parts)


def test_loop_expand_inline_child_package() -> None:
    board = BoardFacade()
    entries = dict(board.legal_entries(board.state))
    backend = ScriptedBackend(
        [
            [
                _tool_call(
                    "board_expand", {"node_id": ROOT_NODE_ID, "action_ids": [entries["e2e4"]]}
                )
            ],
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": entries["e2e4"]})],
        ]
    )
    outcome = _run(
        ArenaDecisionLoop(
            game_id="g3", board=board, backend=backend, model_ref=MODEL_REF, max_rounds=4
        )
    )
    assert outcome.status == "COMMITTED"
    second_request = backend.requests[1]
    tool_messages = [m for m in second_request.messages if m.role is MessageRole.TOOL]
    # Transcript[0] is the harness root preload; the expand result follows it.
    expand_payload = json_payload(tool_messages[1].parts[0].content)
    row = expand_payload["results"][0]
    assert row["uci"] == "e2e4"
    assert row["package"]["state"]["node_id"] == row["child_node_id"]
    assert row["terminal"] is False


def test_loop_provider_timeout_fails_closed() -> None:
    board = BoardFacade()
    backend = ScriptedBackend([ProviderTimeoutError("agy timed out")])
    outcome = _run(
        ArenaDecisionLoop(
            game_id="g4", board=board, backend=backend, model_ref=MODEL_REF, max_rounds=4
        )
    )
    assert outcome.status == "PROVIDER_TIMEOUT_UNKNOWN"
    assert outcome.uci is None
    assert board.turn == "white"


def test_game_full_flow_and_persistence(tmp_path) -> None:
    board = BoardFacade()
    game = ArenaGame(
        game_id=new_game_id(),
        created_at="2026-09-08T00:00:00",
        setup={
            "provider": "antigravity-cli",
            "model": "gemini-3.8-flash-low",
            "effort": "low",
            "human_color": "white",
            "max_rounds": 6,
            "timeout_seconds": 180,
        },
        board=board,
    )
    game.apply_human_move("e2e4")
    assert game.status == "human_turn" or game.status == "model_thinking"
    game.status = "model_thinking"

    backend = ScriptedBackend(
        [
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "e7e5"})],
        ]
    )
    loop = ArenaDecisionLoop(
        game_id=game.game_id, board=game.board, backend=backend, model_ref=MODEL_REF, max_rounds=6
    )
    outcome = _run(loop)
    assert game.record_model_outcome(outcome, model_color=game.model_color) is True
    assert [m.uci for m in game.moves] == ["e2e4", "e7e5"]
    assert game.status == "human_turn"
    assert game.model_note is not None and game.model_note["my_move"] == "e5"

    game.dump(tmp_path)
    restored = load_game(tmp_path / f"{game.game_id}.json")
    assert [m.uci for m in restored.moves] == ["e2e4", "e7e5"]
    assert restored.board.moves == ["e2e4", "e7e5"]
    assert restored.board.turn == "white"


def test_game_records_provider_failure_as_error_not_move(tmp_path) -> None:
    board = BoardFacade()
    game = ArenaGame(
        game_id=new_game_id(),
        created_at="2026-09-08T00:00:01",
        setup={
            "provider": "antigravity-cli",
            "model": "gemini-3.8-flash-low",
            "effort": "low",
            "human_color": "white",
            "max_rounds": 6,
            "timeout_seconds": 180,
        },
        board=board,
    )
    game.apply_human_move("d2d4")
    game.status = "model_thinking"
    backend = ScriptedBackend([ProviderTimeoutError("timeout")])
    outcome = _run(
        ArenaDecisionLoop(
            game_id=game.game_id,
            board=game.board,
            backend=backend,
            model_ref=MODEL_REF,
            max_rounds=6,
        )
    )
    assert game.record_model_outcome(outcome, model_color=game.model_color) is False
    assert len(game.moves) == 1
    assert game.status == "human_turn"
    assert game.last_error and "PROVIDER_TIMEOUT_UNKNOWN" in game.last_error


@pytest.mark.parametrize(
    "fen,turn",
    [
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "white"),
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1", "black"),
    ],
)
def test_board_facade_turn(fen: str, turn: str) -> None:
    assert BoardFacade(start_fen=fen).turn == turn
