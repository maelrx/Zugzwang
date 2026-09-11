"""ZGW-0108 arena service over real HTTP (ephemeral port, scripted backend)."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from tests.unit.test_arena_history import fake_review, wait_analysis
from tests.unit.test_arena_play import ScriptedBackend, _tool_call
from zugzwang_cli.arena.loop import ROOT_NODE_ID
from zugzwang_cli.arena.server import ArenaRequestHandler, ArenaService
from zugzwang_runtime.application.arena_analysis import ArenaAnalysisService


@pytest.fixture()
def arena(tmp_path):  # type: ignore[no-untyped-def]
    shared = ScriptedBackend(
        [
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "e7e5"})],
            [_tool_call("board_finalize", {"node_id": ROOT_NODE_ID, "action_id": "g8f6"})],
        ]
    )
    analysis = ArenaAnalysisService(tmp_path / "reviews", fake_review, {"depth": 20})
    service = ArenaService(
        tmp_path / "arena", backend_factory=lambda *a, **k: shared, analysis=analysis
    )
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", 0), type("H", (ArenaRequestHandler,), {"service": service})
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", service
    httpd.shutdown()
    httpd.server_close()
    analysis.close()


def _request(url: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(json.loads(response.read().decode("utf-8")))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, dict(json.loads(body)) if body else {}


def _wait_idle(base: str, game_id: str, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, state = _request(f"{base}/play/api/games/{game_id}")
        if not state["thinking"]:
            return state
        time.sleep(0.05)
    raise AssertionError("model turn never finished")


def test_providers_catalog_marks_gemini_validated(arena) -> None:
    base, _ = arena
    status, payload = _request(f"{base}/play/api/providers")
    assert status == 200
    gemini = next(p for p in payload["providers"] if p["id"] == "antigravity-cli")
    assert gemini["validated"] is True
    assert any(m["validated"] for m in gemini["models"])


def test_full_game_roundtrip_over_http(arena, tmp_path) -> None:
    base, service = arena
    _, created = _request(
        f"{base}/play/api/games",
        {
            "provider": "antigravity-cli",
            "model": "gemini-3.8-flash-low",
            "effort": "low",
            "human_color": "white",
        },
    )
    game_id = created["id"]
    assert created["status"] == "human_turn"
    assert created["dests"]["e2"] == ["e3", "e4"]

    status, _after_move = _request(f"{base}/play/api/games/{game_id}/moves", {"uci": "e2e4"})
    assert status == 200
    state = _wait_idle(base, game_id)
    assert [m["uci"] for m in state["moves"]] == ["e2e4", "e7e5"]
    assert state["moves"][1]["actor"] == "model"
    assert state["turn"] == "white"

    _request(f"{base}/play/api/games/{game_id}/moves", {"uci": "g1f3"})
    state = _wait_idle(base, game_id)
    assert [m["uci"] for m in state["moves"]] == ["e2e4", "e7e5", "g1f3", "g8f6"]

    status, illegal = _request(f"{base}/play/api/games/{game_id}/moves", {"uci": "e2e5"})
    assert status == 400 and illegal["error"] == "illegal_move"

    listing = _request(f"{base}/play/api/games")[1]
    assert any(g["id"] == game_id for g in listing["games"])

    persisted = json.loads((tmp_path / "arena" / f"{game_id}.json").read_text(encoding="utf-8"))
    assert [m["uci"] for m in persisted["moves"]] == ["e2e4", "e7e5", "g1f3", "g8f6"]
    assert (tmp_path / "arena" / f"{game_id}.pgn").exists()

    assert len(service.games) == 1


def test_unknown_provider_and_unknown_game(arena) -> None:
    base, _ = arena
    code, _ = _request(f"{base}/play/api/games", {"provider": "nope"})
    assert code == 404
    code, payload = _request(f"{base}/play/api/games/missing")
    assert code == 404 and payload["error"] == "unknown_game"


def test_history_analysis_and_pgn_routes(arena) -> None:
    base, service = arena
    _, game = _request(f"{base}/play/api/games", {"human_color": "white"})
    game_id = game["id"]
    assert len(game["positions"]) == 1
    code, payload = _request(f"{base}/play/api/games/{game_id}/analysis", {})
    assert code == 400
    assert "encerrar" in payload["detail"]
    code, _ = _request(f"{base}/play/api/games/{game_id}/retry", {})
    assert code == 400  # cannot force model to play on human's turn
    _request(f"{base}/play/api/games/{game_id}/moves", {"uci": "e2e4"})
    _wait_idle(base, game_id)
    code, finished = _request(f"{base}/play/api/games/{game_id}/resign", {})
    assert code == 200 and finished["status"] == "finished"
    assert len(finished["positions"]) == 3
    assert service.analysis is not None
    wait_analysis(service.analysis, game_id)
    code, review = _request(f"{base}/play/api/games/{game_id}/analysis")
    assert code == 200 and review["status"] == "complete"
    assert len(review["positions"]) == 3
    _, listing = _request(f"{base}/play/api/games")
    assert listing["games"][0]["analysis"]["completed"] == 3
    with urllib.request.urlopen(f"{base}/play/api/games/{game_id}/pgn") as response:
        assert response.headers["Content-Type"].startswith("application/x-chess-pgn")
        assert "1. e4 e5" in response.read().decode()
