"""State reconstruction strategy: the model predicts the FEN.

Input is a move sequence; the output must be a FEN (JSON envelope or raw).
Scoring happens at the coordinator level with formal metrics — this strategy
only parses and returns the prediction.
"""

from __future__ import annotations

import json
from typing import Any, cast

from zugzwang_core.domain.assistance import AssistanceImpact, HClass
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.ports.model import (
    CallContext,
    Message,
    MessageRole,
    ModelRequest,
    OutputConstraint,
    TextPart,
)
from zugzwang_core.ports.strategy import (
    CallRecord,
    Candidate,
    DecisionContext,
    DecisionTrace,
    StrategyDescriptor,
    Verdict,
)


class ReconstructStrategy:
    """Predicts the FEN of a position from its move sequence."""

    strategy_id = "chess.reconstruct"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

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
        obs: dict[str, JsonValue] = (
            cast(dict[str, JsonValue], observation) if isinstance(observation, dict) else {}
        )
        history = obs.get("history")
        moves_text = " ".join(str(m) for m in history) if isinstance(history, list) else ""
        prompt = (
            "You are given a sequence of chess moves in UCI notation:\n"
            f"{moves_text}\n"
            "Reconstruct the resulting position and reply with the FEN string "
            'as JSON: {"fen": "..."}'
        )
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text=prompt),)),),
            output_constraint=OutputConstraint(format="text"),
            extensions={"chess.strategy": "reconstruct"},
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-reconstruct:{context.seed}",
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
        fen = self._extract_fen(raw)
        impact = AssistanceImpact(h=HClass.H0, source="formal_parser")
        if fen is None:
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
                verdicts=(Verdict(kind="parse_error", message="no FEN found in output"),),
                final_action=None,
                termination_reason="parse_error",
            )
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
            candidates=(Candidate(action=fen, origin="reconstruction"),),
            verdicts=(Verdict(kind="parse_ok", message="fen parsed", assistance_impact=impact),),
            final_action=fen,
            termination_reason="selected",
            assistance_impacts=(impact,),
        )

    @staticmethod
    def _extract_fen(raw: str) -> str | None:
        from ..codecs.fen import parse_fen

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            raw_payload: dict[Any, Any] = cast(dict[Any, Any], payload)
            fen_value = raw_payload.get("fen")
            if isinstance(fen_value, str):
                parsed = parse_fen(fen_value, raise_on_invalid=False)
                return parsed.fen if parsed is not None else None
        for token in raw.replace(",", " ").split():
            if "/" in token and len(token.split("/")) == 8:
                parsed = parse_fen(token, raise_on_invalid=False)
                if parsed is not None:
                    return parsed.fen
        return None
