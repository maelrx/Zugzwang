from __future__ import annotations

import re
from time import perf_counter
from typing import Any

from zugzwang.providers.base import ProviderResponse


UCI_PATTERN = re.compile(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", flags=re.IGNORECASE)


class MockProvider:
    """Deterministic local provider for tests and offline development."""

    def complete(
        self, messages: list[dict[str, str]], model_config: dict[str, Any]
    ) -> ProviderResponse:
        started = perf_counter()
        content = messages[-1]["content"] if messages else ""
        text = self._generate(content)
        latency_ms = int((perf_counter() - started) * 1000)
        model = str(model_config.get("model", "mock-1"))
        return ProviderResponse(
            text=text,
            model=model,
            input_tokens=max(1, len(content.split())),
            output_tokens=max(1, len(text.split())),
            latency_ms=latency_ms,
            cost_usd=0.0,
        )

    def _generate(self, prompt: str) -> str:
        legal_moves = self._extract_legal_moves(prompt)
        if "respond with the action only" in prompt.lower():
            if "observation (legal moves):" in prompt.lower() and legal_moves:
                return f"make_move {legal_moves[0]}"
            if "observation (current board):" in prompt.lower():
                return "get_legal_moves"
            return "get_current_board"

        if legal_moves:
            return legal_moves[0]

        any_uci = UCI_PATTERN.findall(prompt)
        return any_uci[0].lower() if any_uci else "e2e4"

    def _extract_legal_moves(self, text: str) -> list[str]:
        lines = text.splitlines()
        for line in reversed(lines):
            lowered = line.lower()
            if "legal moves" in lowered:
                return [move.lower() for move in UCI_PATTERN.findall(line)]
        return []
