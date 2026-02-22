from __future__ import annotations

import json
import re
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from zugzwang.experiments.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[2]
UCI_PATTERN = re.compile(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", re.IGNORECASE)


def _pick_move_from_prompt(prompt: str) -> str:
    for line in reversed(prompt.splitlines()):
        if "legal moves" in line.lower():
            moves = [m.lower() for m in UCI_PATTERN.findall(line)]
            if moves:
                return moves[0]
    moves = [m.lower() for m in UCI_PATTERN.findall(prompt)]
    return moves[0] if moves else "e2e4"


@contextmanager
def _mock_server(
    responder: Callable[[dict[str, Any], str], tuple[int, dict[str, Any] | str]]
):
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw)
            status, body = responder(payload, self.path)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if isinstance(body, str):
                self.wfile.write(body.encode("utf-8"))
            else:
                self.wfile.write(json.dumps(body).encode("utf-8"))

        def log_message(self, format, *args):  # noqa: A003
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_runner_works_with_mocked_zai_server(tmp_path: Path, monkeypatch) -> None:
    def responder(payload: dict[str, Any], path: str) -> tuple[int, dict[str, Any]]:
        messages = payload.get("messages", [])
        prompt = messages[-1]["content"] if messages else ""
        move = _pick_move_from_prompt(prompt)
        return (
            200,
            {
                "choices": [{"message": {"content": move}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    with _mock_server(responder) as base_url:
        monkeypatch.setenv("ZAI_API_KEY", "test-zai-key")
        monkeypatch.setenv("ZAI_BASE_URL", base_url)

        config_path = ROOT / "configs" / "baselines" / "best_known_start_zai_glm5.yaml"
        runner = ExperimentRunner(
            config_path=config_path,
            overrides=[
                "experiment.target_valid_games=1",
                "experiment.max_games=1",
                "runtime.max_plies=6",
                f"runtime.output_dir={tmp_path.as_posix()}",
            ],
        )
        payload = runner.run()

    run_dir = Path(payload["run_dir"])
    game = json.loads((run_dir / "games" / "game_0001.json").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "_run.json").read_text(encoding="utf-8"))

    assert payload["games_written"] == 1
    assert game["players"]["black"]["provider"] == "zai"
    assert game["token_usage"]["input"] > 0
    assert "ZAI_API_KEY" in metadata["required_env_vars"]


def test_non_retryable_zai_http_error_stops_retries(tmp_path: Path, monkeypatch) -> None:
    calls = {"count": 0}

    def responder(payload: dict[str, Any], path: str) -> tuple[int, dict[str, Any]]:
        calls["count"] += 1
        return (401, {"error": {"message": "unauthorized"}})

    with _mock_server(responder) as base_url:
        monkeypatch.setenv("ZAI_API_KEY", "test-zai-key")
        monkeypatch.setenv("ZAI_BASE_URL", base_url)

        config_path = ROOT / "configs" / "baselines" / "best_known_start_zai_glm5.yaml"
        runner = ExperimentRunner(
            config_path=config_path,
            overrides=[
                "experiment.target_valid_games=1",
                "experiment.max_games=1",
                "runtime.max_plies=2",
                f"runtime.output_dir={tmp_path.as_posix()}",
            ],
        )
        payload = runner.run()

    run_dir = Path(payload["run_dir"])
    game = json.loads((run_dir / "games" / "game_0001.json").read_text(encoding="utf-8"))
    black_move = next(move for move in game["moves"] if move["color"] == "black")

    assert calls["count"] == 1
    assert black_move["move_decision"]["error"] == "provider_auth"
