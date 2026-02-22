from __future__ import annotations

import os
import random
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import chess
import chess.engine

from zugzwang.core.models import GameState, MoveDecision
from zugzwang.core.protocol import (
    build_agentic_prompt,
    parse_agentic_action,
)
from zugzwang.providers.base import (
    ProviderError,
    ProviderInterface,
    ProviderResponse,
    should_retry_provider_error,
)
from zugzwang.providers.registry import create_provider
from zugzwang.strategy.context import build_direct_prompt
from zugzwang.strategy.validator import build_retry_feedback, validate_move_response


class PlayerInterface(ABC):
    @abstractmethod
    def choose_move(self, game_state: GameState) -> MoveDecision:
        raise NotImplementedError


def _provider_error_code(error: ProviderError) -> str:
    if error.category:
        return f"provider_{error.category}"
    return "provider_error"


class RandomPlayer(PlayerInterface):
    def __init__(self, name: str, rng: random.Random | None = None) -> None:
        self.name = name
        self._rng = rng or random.Random()

    def choose_move(self, game_state: GameState) -> MoveDecision:
        move = self._rng.choice(game_state.legal_moves_uci)
        return MoveDecision(
            move_uci=move,
            move_san="",
            raw_response=move,
            parse_ok=True,
            is_legal=True,
            retry_count=0,
            tokens_input=0,
            tokens_output=0,
            latency_ms=0,
            provider_model="random",
            provider_calls=0,
        )


class LLMPlayer(PlayerInterface):
    def __init__(
        self,
        name: str,
        provider: ProviderInterface,
        model: str,
        model_config: dict[str, Any],
        protocol_mode: str,
        strategy_config: dict[str, Any],
        rng: random.Random | None = None,
    ) -> None:
        self.name = name
        self.provider = provider
        self.model = model
        self.model_config = model_config
        self.protocol_mode = protocol_mode
        self.strategy_config = strategy_config
        self._rng = rng or random.Random()

    def choose_move(self, game_state: GameState) -> MoveDecision:
        if self.protocol_mode == "agentic_compat":
            return self._choose_move_agentic(game_state)
        return self._choose_move_direct(game_state)

    def _choose_move_direct(self, game_state: GameState) -> MoveDecision:
        validation_cfg = self.strategy_config.get("validation", {})
        move_retries = int(validation_cfg.get("move_retries", 3))
        feedback_level = str(validation_cfg.get("feedback_level", "rich"))

        last_response = ""
        total_in = 0
        total_out = 0
        total_latency = 0
        provider_calls = 0
        total_cost_usd = 0.0
        last_error: str | None = None
        retry_feedback: str | None = None

        for retry in range(move_retries + 1):
            prompt = build_direct_prompt(
                game_state,
                self.strategy_config,
                retry_feedback=retry_feedback if retry > 0 else None,
            )

            try:
                response = self._call_provider([{"role": "user", "content": prompt}])
            except ProviderError as exc:
                last_error = _provider_error_code(exc)
                retry_feedback = "Provider call failed. Return exactly one legal UCI move."
                if not should_retry_provider_error(exc):
                    break
                continue
            provider_calls += 1
            total_in += response.input_tokens
            total_out += response.output_tokens
            total_latency += response.latency_ms
            total_cost_usd += response.cost_usd
            last_response = response.text

            validation = validate_move_response(response.text, game_state.legal_moves_uci)
            if not (validation.parse_ok and validation.is_legal and validation.move_uci):
                last_error = validation.error_code or "validation_failed"
                retry_feedback = build_retry_feedback(
                    validation=validation,
                    feedback_level=feedback_level,
                    legal_moves_uci=game_state.legal_moves_uci,
                    phase=game_state.phase,
                )
                continue

            return MoveDecision(
                move_uci=validation.move_uci,
                move_san="",
                raw_response=response.text,
                parse_ok=True,
                is_legal=True,
                retry_count=retry,
                tokens_input=total_in,
                tokens_output=total_out,
                latency_ms=total_latency,
                provider_model=response.model,
                provider_calls=provider_calls,
                feedback_level=feedback_level,
                cost_usd=total_cost_usd,
            )

        fallback_move = self._rng.choice(game_state.legal_moves_uci)
        return MoveDecision(
            move_uci=fallback_move,
            move_san="",
            raw_response=last_response,
            parse_ok=False,
            is_legal=True,
            retry_count=move_retries,
            tokens_input=total_in,
            tokens_output=total_out,
            latency_ms=total_latency,
            provider_model=self.model,
            provider_calls=provider_calls,
            feedback_level=feedback_level,
            error=last_error or "fallback_random",
            cost_usd=total_cost_usd,
        )

    def _choose_move_agentic(self, game_state: GameState) -> MoveDecision:
        validation_cfg = self.strategy_config.get("validation", {})
        move_retries = int(validation_cfg.get("move_retries", 3))
        max_turns = int(validation_cfg.get("max_agentic_turns", 6))
        feedback_level = str(validation_cfg.get("feedback_level", "moderate"))

        total_in = 0
        total_out = 0
        total_latency = 0
        provider_calls = 0
        total_cost_usd = 0.0
        last_response = ""
        last_error: str | None = None

        for retry in range(move_retries + 1):
            conversation = [{"role": "user", "content": build_agentic_prompt(game_state)}]
            selected_move: str | None = None
            provider_model = self.model
            provider_hard_fail = False

            for _ in range(max_turns):
                try:
                    response = self._call_provider(conversation)
                except ProviderError as exc:
                    last_error = _provider_error_code(exc)
                    provider_hard_fail = not should_retry_provider_error(exc)
                    break
                provider_calls += 1
                total_in += response.input_tokens
                total_out += response.output_tokens
                total_latency += response.latency_ms
                total_cost_usd += response.cost_usd
                provider_model = response.model
                last_response = response.text

                action, arg = parse_agentic_action(response.text)
                if action == "make_move" and arg:
                    selected_move = arg
                    break
                if action == "get_current_board":
                    observation = f"Observation (current board): FEN: {game_state.fen}"
                    conversation.append({"role": "assistant", "content": response.text})
                    conversation.append({"role": "user", "content": observation})
                    continue
                if action == "get_legal_moves":
                    legal = ", ".join(game_state.legal_moves_uci)
                    observation = f"Observation (legal moves): {legal}"
                    conversation.append({"role": "assistant", "content": response.text})
                    conversation.append({"role": "user", "content": observation})
                    continue

                conversation.append({"role": "assistant", "content": response.text})
                conversation.append(
                    {
                        "role": "user",
                        "content": (
                            "Invalid action. Reply with one of: get_current_board, "
                            "get_legal_moves, make_move <UCI move>."
                        ),
                    }
                )

            if selected_move and selected_move in game_state.legal_moves_uci:
                return MoveDecision(
                    move_uci=selected_move,
                    move_san="",
                    raw_response=last_response,
                    parse_ok=True,
                    is_legal=True,
                    retry_count=retry,
                    tokens_input=total_in,
                    tokens_output=total_out,
                    latency_ms=total_latency,
                    provider_model=provider_model,
                    provider_calls=provider_calls,
                    feedback_level=feedback_level,
                    cost_usd=total_cost_usd,
                )
            if provider_hard_fail:
                break
            last_error = "agentic_move_invalid_or_missing"

        fallback_move = self._rng.choice(game_state.legal_moves_uci)
        return MoveDecision(
            move_uci=fallback_move,
            move_san="",
            raw_response=last_response,
            parse_ok=False,
            is_legal=True,
            retry_count=move_retries,
            tokens_input=total_in,
            tokens_output=total_out,
            latency_ms=total_latency,
            provider_model=self.model,
            provider_calls=provider_calls,
            feedback_level=feedback_level,
            error=last_error or "fallback_random",
            cost_usd=total_cost_usd,
        )

    def _call_provider(self, messages: list[dict[str, str]]) -> ProviderResponse:
        model_config = {"model": self.model}
        model_config.update(self.model_config)
        retries = int(self.strategy_config.get("validation", {}).get("provider_retries", 2))
        backoff_seconds = float(self.strategy_config.get("validation", {}).get("provider_backoff_seconds", 0.25))
        last_error: ProviderError | None = None
        for attempt in range(retries + 1):
            try:
                return self.provider.complete(messages=messages, model_config=model_config)
            except ProviderError as exc:
                last_error = exc
                if attempt >= retries or not should_retry_provider_error(exc):
                    break
                time.sleep(backoff_seconds * (2**attempt))
        if last_error is not None:
            raise last_error
        raise ProviderError("Unknown provider error")


class EnginePlayer(RandomPlayer):
    def __init__(
        self,
        name: str,
        rng: random.Random | None = None,
        path: str | None = None,
        depth: int = 8,
        movetime_ms: int | None = None,
        threads: int = 1,
        hash_mb: int = 64,
    ) -> None:
        super().__init__(name=name, rng=rng)
        self.path = path or os.environ.get("STOCKFISH_PATH") or "stockfish"
        self.depth = depth
        self.movetime_ms = movetime_ms
        self.threads = threads
        self.hash_mb = hash_mb
        self._engine: chess.engine.SimpleEngine | None = None

    def _ensure_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is not None:
            return self._engine
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        except FileNotFoundError as exc:
            raise ProviderError(
                "Engine binary not found. Set STOCKFISH_PATH or players.<color>.path for type=engine.",
                category="engine_unavailable",
                retryable=False,
            ) from exc
        except Exception as exc:  # pragma: no cover - rare engine startup edge-cases.
            raise ProviderError(
                f"Engine startup failed: {exc}",
                category="engine_unavailable",
                retryable=False,
            ) from exc

        try:
            self._engine.configure({"Threads": self.threads, "Hash": self.hash_mb})
        except chess.engine.EngineError:
            # Keep running with engine defaults if one of these options is unsupported.
            pass
        return self._engine

    def _limit(self) -> chess.engine.Limit:
        if self.movetime_ms is not None:
            return chess.engine.Limit(time=max(0.001, self.movetime_ms / 1000))
        return chess.engine.Limit(depth=self.depth)

    def close(self) -> None:
        if self._engine is None:
            return
        try:
            self._engine.quit()
        except Exception:
            pass
        self._engine = None

    def __del__(self) -> None:  # pragma: no cover - cleanup only.
        self.close()

    def choose_move(self, game_state: GameState) -> MoveDecision:
        started = time.perf_counter()
        fallback_move = self._rng.choice(game_state.legal_moves_uci)
        move_uci = fallback_move
        parse_ok = False
        is_legal = True
        error: str | None = None
        provider_calls = 0

        try:
            board = chess.Board(game_state.fen)
            result = self._ensure_engine().play(board, self._limit())
            provider_calls = 1
            if result.move is None:
                error = "engine_no_move"
            else:
                candidate = result.move.uci()
                if candidate in game_state.legal_moves_uci:
                    move_uci = candidate
                    parse_ok = True
                else:
                    error = "engine_illegal_move"
        except ProviderError as exc:
            error = _provider_error_code(exc)
        except Exception as exc:  # pragma: no cover - defensive against engine runtime failures.
            error = f"engine_error:{exc.__class__.__name__.lower()}"

        latency_ms = int((time.perf_counter() - started) * 1000)
        return MoveDecision(
            move_uci=move_uci,
            move_san="",
            raw_response=move_uci,
            parse_ok=parse_ok,
            is_legal=is_legal,
            retry_count=0,
            tokens_input=0,
            tokens_output=0,
            latency_ms=latency_ms,
            provider_model=f"engine:{Path(self.path).name}",
            provider_calls=provider_calls,
            error=error,
            cost_usd=0.0,
        )


def build_player(
    player_config: dict[str, Any],
    protocol_mode: str,
    strategy_config: dict[str, Any],
    rng: random.Random,
) -> PlayerInterface:
    player_type = player_config.get("type")
    name = player_config.get("name", player_type)
    if player_type == "random":
        return RandomPlayer(name=name, rng=rng)
    if player_type == "engine":
        return EnginePlayer(
            name=name,
            rng=rng,
            path=player_config.get("path"),
            depth=int(player_config.get("depth", 8)),
            movetime_ms=(
                int(player_config["movetime_ms"])
                if player_config.get("movetime_ms") is not None
                else None
            ),
            threads=int(player_config.get("threads", 1)),
            hash_mb=int(player_config.get("hash_mb", 64)),
        )
    if player_type == "llm":
        provider_name = player_config.get("provider")
        model = player_config.get("model")
        provider = create_provider(provider_name)
        passthrough_keys = {
            "temperature",
            "top_p",
            "max_tokens",
            "pricing_mode",
        }
        model_config = {
            key: player_config[key]
            for key in passthrough_keys
            if key in player_config
        }
        return LLMPlayer(
            name=name,
            provider=provider,
            model=model,
            model_config=model_config,
            protocol_mode=protocol_mode,
            strategy_config=strategy_config,
            rng=rng,
        )
    raise ProviderError(
        f"Unsupported player type: {player_type}",
        category="invalid_request",
        retryable=False,
    )
