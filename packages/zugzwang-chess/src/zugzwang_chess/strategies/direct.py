"""Chess R0 strategy: one observation, one inference, one UCI parse.

The model receives a text observation (FEN/history per protocol) and answers
with a UCI move (raw text or JSON envelope). No legal-action grounding — that
is R1. Parsing and legality stay separate verdicts.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

from zugzwang_chess.strategies._calls import new_call_attempt_id
from zugzwang_core.domain.assistance import AssistanceImpact, HClass
from zugzwang_core.domain.errors import OutputParseError
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.domain.prompt_program import PromptProgram
from zugzwang_core.ports.model import (
    CallContext,
    Message,
    MessageRole,
    ModelRequest,
    OutputConstraint,
)
from zugzwang_core.ports.strategy import (
    CallRecord,
    Candidate,
    DecisionContext,
    DecisionTrace,
    StrategyDescriptor,
    Verdict,
)

from ._image import build_message_parts
from ._knowledge import knowledge_impacts, render_knowledge_section
from ._prompt_hooks import append_retry_feedback, apply_prompt_override


def build_observation_text(observation: dict[str, JsonValue]) -> str:
    """Deterministic text rendering of a chess observation (no SAN leakage)."""
    lines: list[str] = []
    fen = observation.get("fen")
    if fen:
        lines.append(f"FEN: {fen}")
    side = observation.get("side_to_move")
    if side:
        lines.append(f"Side to move: {side}")
    move_number = observation.get("move_number")
    if move_number is not None:
        lines.append(f"Move number: {move_number}")
    history = observation.get("history")
    if isinstance(history, list):
        lines.append("Move history: " + " ".join(str(h) for h in history))
    elif isinstance(history, str) and history:
        lines.append("Move history: " + history)
    ascii_board = observation.get("ascii")
    if ascii_board:
        lines.append(str(ascii_board))
    lines.append("Reply with a single move in UCI notation (e.g. e2e4).")
    return "\n".join(lines)


class ChessDirectStrategy:
    """R0 for standard chess: UCI in, UCI out."""

    strategy_id = "chess.direct"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, *, parse_json: bool = True) -> None:
        self._parse_json = parse_json
        self._program = PromptProgram(
            template_id="chess.direct.move",
            version="1.0.0",
            system_instructions=(
                "You are playing standard chess. You receive the position and the "
                "move history. Choose a move."
            ),
            strategy_stage="decide",
        )

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R0",
            declared_assistance_h="H2",
            declared_assistance_k="K0",
            consumes_legal_actions=False,
            produces_candidates=False,
            max_model_calls=1,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        text = self._observation_text(observation)
        knowledge_section = render_knowledge_section(context.knowledge)
        if knowledge_section:
            text = f"{text}\n\n{knowledge_section}"
        side = "unknown"
        if isinstance(observation, dict):
            side_value = cast(dict[str, Any], observation).get("side_to_move")
            if side_value is not None:
                side = str(side_value)
        program = apply_prompt_override(self._program, context)
        prompt_text = program.render(text)
        prompt_text = append_retry_feedback(prompt_text, context)
        parts, required_capabilities = build_message_parts(
            cast(dict[str, JsonValue], observation),
            prompt_text,
            artifact_store=context.artifact_store,
        )
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=parts),),
            output_constraint=OutputConstraint(format="text"),
            required_capabilities=required_capabilities,
            extensions={
                "chess.strategy": "direct",
                "chess.parse_json": self._parse_json,
                "prompt_program": self._program.template_id,
                "prompt_program_version": self._program.version,
                "prompt_hash": self._program.hash(text),
            },
        )
        call_context = CallContext(
            attempt_id=new_call_attempt_id(),
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-direct:{side}:{context.seed}",
        )
        try:
            result = await context.backend.infer(request, call_context)
        except Exception as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R0",
                verdicts=(
                    Verdict(kind="provider_error", message=getattr(exc, "stable_code", str(exc))),
                ),
                final_action=None,
                termination_reason="provider_error",
            )
        response = result.response
        raw = response.text().strip()
        fen_hint: str | None = None
        if isinstance(observation, dict):
            fen_value = cast(dict[str, Any], observation).get("fen")
            if isinstance(fen_value, str):
                fen_hint = fen_value
        try:
            move_uci = self._extract_move(raw, fen_hint)
        except OutputParseError as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R0",
                calls=(
                    CallRecord(
                        attempt_id=call_context.attempt_id or "att-placeholder",
                        response_ok=True,
                        usage=response.usage,
                    ),
                ),
                verdicts=(Verdict(kind="parse_error", message=exc.user_message),),
                final_action=None,
                termination_reason="parse_error",
            )
        impact = AssistanceImpact(h=HClass.H0, source="formal_parser")
        impacts = (impact, *knowledge_impacts(context.knowledge))
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R0",
            calls=(
                CallRecord(
                    attempt_id=call_context.attempt_id or "att-placeholder",
                    response_ok=True,
                    usage=response.usage,
                ),
            ),
            candidates=(Candidate(action=move_uci, origin="model_output"),),
            verdicts=(Verdict(kind="parse_ok", message="uci parsed", assistance_impact=impact),),
            final_action=move_uci,
            termination_reason="selected",
            assistance_impacts=impacts,
        )

    def _extract_move(self, raw: str, fen: str | None = None) -> str:
        """Extract a UCI move from raw text (JSON envelope, UCI or SAN)."""
        if self._parse_json:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                raw_payload: dict[Any, Any] = cast(dict[Any, Any], payload)
                move = raw_payload.get("move") or raw_payload.get("action")
                if isinstance(move, str):
                    return move.strip()
            elif raw:
                pass
        from ..codecs.uci import parse_uci

        tokens = [token.strip(' *`_.,;:()[]{}!"') for token in raw.replace(",", " ").split()]
        for token in tokens:
            candidate = parse_uci(token, raise_on_invalid=False)
            if candidate is not None:
                return candidate.uci
        if fen is not None:
            san_move = self._extract_san(raw, fen)
            if san_move is not None:
                return san_move
        raise OutputParseError(
            "no UCI move found in model output",
            technical_context=f"output={raw[:120]!r}",
        )

    @staticmethod
    def _extract_san(raw: str, fen: str) -> str | None:
        """Try to parse a SAN token against the observation FEN (G1)."""
        import chess

        try:
            board = chess.Board(fen)
        except ValueError:
            return None
        for token in raw.replace(",", " ").split():
            candidate = token.strip()
            if not re.fullmatch(
                r"[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?|O-O(-O)?[+#]?", candidate
            ):
                continue
            try:
                move = board.parse_san(candidate)
            except ValueError:
                continue
            return move.uci()
        return None

    @staticmethod
    def _observation_text(observation: Any) -> str:
        if isinstance(observation, dict):
            return build_observation_text(cast(dict[str, JsonValue], observation))
        return str(cast(object, observation))
