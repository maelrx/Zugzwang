"""Arena HTTP service (local-only): the play backend behind the webapp.

stdlib only — no new dependency. Binds 127.0.0.1 by default. Run from the
repo root:

    uv run python -m zugzwang_cli.arena.server --port 4191

The webapp reaches it through the vite dev-server proxy at ``/play``.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from .game import ArenaGame, load_game, new_game_id
from .loop import DEFAULT_DIRECTIVE, ArenaDecisionLoop
from .positions import BoardFacade
from .providers import REGISTRY, build_backend, providers_catalog

DEFAULT_PORT = 4191
DEFAULT_DIR = Path("out/arena")


class ArenaService:
    """Game store + model-turn runner (framework-free, testable)."""

    def __init__(
        self,
        arena_dir: Path,
        *,
        backend_factory: Any = None,
    ) -> None:
        self.arena_dir = arena_dir
        self._backend_factory = backend_factory or build_backend
        self.games: dict[str, ArenaGame] = {}
        self._load_existing()
        self._migrate_finished_threads()

    # -- store ------------------------------------------------------------------

    def _load_existing(self) -> None:
        if not self.arena_dir.exists():
            return
        for path in sorted(self.arena_dir.glob("arena-*.json")):
            try:
                game = load_game(path, call_sink=self._call_sink_for(path.stem))
                self.games[game.game_id] = game
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue

    def _migrate_finished_threads(self) -> None:
        for game in self.games.values():
            if game.status == "model_thinking":
                game.status = "human_turn"

    def _call_sink_for(self, game_id: str):  # type: ignore[no-untyped-def]
        log_path = self.arena_dir / f"{game_id}-calls.jsonl"

        def sink(record: dict[str, Any]) -> None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(
                {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}, ensure_ascii=False
            )
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

        return sink

    # -- API --------------------------------------------------------------------

    def create_game(self, setup: dict[str, Any]) -> ArenaGame:
        provider_id = str(setup.get("provider") or "antigravity-cli")
        if provider_id not in REGISTRY:
            raise KeyError(f"unknown provider {provider_id!r}")
        board = BoardFacade(
            start_fen=setup.get("start_fen") or None,
            ascii_enabled=bool(setup.get("ascii", False)),
            history_plies=int(setup.get("history_plies", 12)),
        )
        game = ArenaGame(
            game_id=new_game_id(),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            setup={
                "provider": provider_id,
                "model": setup.get("model"),
                "effort": setup.get("effort"),
                "human_color": "black" if setup.get("human_color") == "black" else "white",
                "max_rounds": max(1, min(8, int(setup.get("max_rounds", 6)))),
                "ascii": bool(setup.get("ascii", False)),
                "history_plies": max(0, min(60, int(setup.get("history_plies", 12)))),
                "directive": (setup.get("directive") or "").strip() or None,
                "timeout_seconds": float(setup.get("timeout_seconds") or 180),
            },
            board=board,
        )
        with game.lock:
            self.games[game.game_id] = game
            if game.model_color == "white":
                game.status = "model_thinking"
                self._spawn_model_turn(game)
            else:
                game.status = "human_turn"
            game.dump(self.arena_dir)
        return game

    def retry_model_turn(self, game_id: str) -> ArenaGame:
        game = self._game(game_id)
        with game.lock:
            if game.status != "human_turn" or game.board.terminal:
                raise ValueError("game is not in a retryable state")
            game.status = "model_thinking"
            self._spawn_model_turn(game)
            game.dump(self.arena_dir)
        return game

    def apply_move(self, game_id: str, uci: str) -> ArenaGame:
        game = self._game(game_id)
        with game.lock:
            game.apply_human_move(uci)
            game.dump(self.arena_dir)
            if game.status == "model_thinking":
                self._spawn_model_turn(game)
        return game

    def resign(self, game_id: str) -> ArenaGame:
        game = self._game(game_id)
        with game.lock:
            game.resign()
            game.dump(self.arena_dir)
        return game

    def _game(self, game_id: str) -> ArenaGame:
        game = self.games.get(game_id)
        if game is None:
            raise KeyError(game_id)
        return game

    # -- model turn ----------------------------------------------------------------

    def _spawn_model_turn(self, game: ArenaGame) -> None:
        thread = threading.Thread(target=self._run_model_turn, args=(game,), daemon=True)
        thread.start()

    def _run_model_turn(self, game: ArenaGame) -> None:
        sink = self._call_sink_for(game.game_id)
        game.call_sink = sink
        loop = ArenaDecisionLoop(
            game_id=game.game_id,
            board=game.board,
            backend=self._backend_factory(
                str(game.setup["provider"]),
                model=game.setup.get("model"),
                effort=game.setup.get("effort"),
                timeout_seconds=float(game.setup["timeout_seconds"]),
            ),
            model_ref=_model_ref(game),
            max_rounds=int(game.setup["max_rounds"]),
            directive=str(game.setup.get("directive") or DEFAULT_DIRECTIVE),
            prior_note=game.model_note,
            call_sink=sink,
        )
        try:
            outcome = asyncio.run(loop.run())
        except Exception as exc:
            outcome = _thread_failure(exc)
        with game.lock:
            game.record_model_outcome(outcome, model_color=game.model_color)
            game.dump(self.arena_dir)


def _thread_failure(exc: Exception):  # type: ignore[no-untyped-def]
    from .loop import DecisionOutcome

    return DecisionOutcome(status="PROTOCOL_ERROR", error=f"{type(exc).__name__}: {exc}")


def _model_ref(game: ArenaGame):  # type: ignore[no-untyped-def]
    from zugzwang_core.ports.model import ModelRef

    return ModelRef(
        backend=str(game.setup.get("provider", "arena")),
        provider=str(game.setup.get("provider", "arena")),
        model=str(game.setup.get("model") or "default"),
    )


class ArenaRequestHandler(BaseHTTPRequestHandler):
    service: ArenaService
    server_version = "zugzwang-arena/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        pass  # keep the service quiet; evidence lives in the JSONL logs

    # -- plumbing -------------------------------------------------------------

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            value: Any = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(value, dict):
            return {}
        return cast("dict[str, Any]", value)

    def _segments(self) -> list[str]:
        return [segment for segment in urlparse(self.path).path.split("/") if segment]

    # -- routing --------------------------------------------------------------

    def do_GET(self) -> None:
        segments = self._segments()  # ["play", "api", ...]
        if segments[:2] != ["play", "api"]:
            self._json({"error": "not_found"}, 404)
            return
        route = segments[2:]
        if route == ["health"]:
            self._json({"ok": True, "games": len(self.service.games)})
            return
        if route == ["providers"]:
            self._json({"providers": providers_catalog()})
            return
        if route == ["games"]:
            games = sorted(self.service.games.values(), key=lambda g: g.created_at, reverse=True)
            self._json({"games": [game.summary() for game in games]})
            return
        if len(route) == 2 and route[0] == "games":
            game = self.service.games.get(route[1])
            if game is None:
                self._json({"error": "unknown_game"}, 404)
                return
            self._json(game.to_state())
            return
        self._json({"error": "not_found"}, 404)

    def do_POST(self) -> None:
        segments = self._segments()
        if segments[:2] != ["play", "api"]:
            self._json({"error": "not_found"}, 404)
            return
        route = segments[2:]
        try:
            if route == ["games"]:
                game = self.service.create_game(self._read_json())
                self._json(game.to_state())
                return
            if len(route) == 3 and route[0] == "games":
                action = route[2]
                if action == "moves":
                    uci = str(self._read_json().get("uci", ""))
                    try:
                        game = self.service.apply_move(route[1], uci)
                    except ValueError as exc:
                        self._json({"error": "illegal_move", "detail": str(exc)}, 400)
                        return
                    self._json(game.to_state())
                    return
                if action == "retry":
                    self._json(self.service.retry_model_turn(route[1]).to_state())
                    return
                if action == "resign":
                    self._json(self.service.resign(route[1]).to_state())
                    return
            self._json({"error": "not_found"}, 404)
        except KeyError:
            self._json({"error": "unknown_game"}, 404)


def serve(
    *, host: str = "127.0.0.1", port: int = DEFAULT_PORT, arena_dir: Path | None = None
) -> None:
    directory = arena_dir or Path(os.environ.get("ZGW_ARENA_DIR", DEFAULT_DIR))
    service = ArenaService(directory)
    handler = type("BoundArenaHandler", (ArenaRequestHandler,), {"service": service})
    httpd = ThreadingHTTPServer((host, port), handler)
    print(
        f"zugzwang arena: http://{host}:{httpd.server_address[1]}/play/api/health → {directory.resolve()}"
    )
    with contextlib.suppress(KeyboardInterrupt):
        httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Zugzwang arena play service (ZGW-0108)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--arena-dir", default=None)
    args = parser.parse_args()
    serve(
        host=args.host,
        port=args.port,
        arena_dir=Path(args.arena_dir) if args.arena_dir else None,
    )


if __name__ == "__main__":
    main()
