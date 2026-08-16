"""Structured strategy (R3): typed pipeline in one structured response.

Stages: analyze → propose candidates → estimate → choose → verify. The
manifest differentiates single-structured-response from separate calls;
this implementation uses ONE structured JSON response (calls=1), recorded
explicitly in the DecisionTrace.
"""

from __future__ import annotations

import json
from typing import Any, cast

from zugzwang_core.domain.assistance import AssistanceImpact, HClass
from zugzwang_core.domain.errors import OutputParseError
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

from .direct import build_observation_text

OUTPUT_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "analysis": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "move": {"type": "string"},
                    "score": {"type": "number"},
                    "rationale": {"type": "string"},
                },
                "required": ["move"],
            },
        },
        "chosen_move": {"type": "string"},
    },
    "required": ["analysis", "candidates", "chosen_move"],
}


class StructuredStrategy:
    """R3: single structured response with candidates and selection."""

    strategy_id = "chess.structured"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, *, max_candidates: int = 3) -> None:
        self._max_candidates = max_candidates

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R3",
            declared_assistance_h="H4",
            declared_assistance_k="K0",
            consumes_legal_actions=False,
            produces_candidates=True,
            max_model_calls=1,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        obs: dict[str, JsonValue] = (
            cast_obs(cast(dict[Any, Any], observation)) if isinstance(observation, dict) else {}
        )
        prompt = build_observation_text(obs) + (
            "\nRespond with JSON only: analysis, up to "
            f"{self._max_candidates} candidate moves with scores, and your chosen move."
        )
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text=prompt),)),),
            output_constraint=OutputConstraint.model_validate(
                {"format": "json_schema", "schema": OUTPUT_SCHEMA}
            ),
            extensions={"chess.strategy": "structured"},
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-structured:{context.seed}",
        )
        try:
            result = await context.backend.infer(request, call_context)
        except Exception as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R3",
                verdicts=(
                    Verdict(kind="provider_error", message=getattr(exc, "stable_code", str(exc))),
                ),
                final_action=None,
                termination_reason="provider_error",
            )
        response = result.response
        raw = response.text().strip()
        try:
            payload = self._parse_payload(raw)
        except OutputParseError as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R3",
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
        candidates_raw: list[Any] = list(cast(list[Any], payload.get("candidates") or []))
        candidates: list[Candidate] = []
        for raw_candidate_raw in candidates_raw[: self._max_candidates]:
            if isinstance(raw_candidate_raw, dict):
                raw_candidate: dict[str, Any] = cast(dict[str, Any], raw_candidate_raw)
                move = raw_candidate.get("move")
                if isinstance(move, str):
                    candidates.append(
                        Candidate(
                            action=move,
                            origin="structured_proposal",
                            score=(
                                float(raw_candidate["score"])
                                if isinstance(raw_candidate.get("score"), (int, float))
                                else None
                            ),
                        )
                    )
        chosen = payload.get("chosen_move")
        if not isinstance(chosen, str) or not chosen:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R3",
                calls=(
                    CallRecord(
                        attempt_id=call_context.attempt_id or "att-placeholder",
                        response_ok=True,
                        usage=response.usage,
                    ),
                ),
                verdicts=(Verdict(kind="parse_error", message="no chosen_move in output"),),
                final_action=None,
                termination_reason="parse_error",
            )
        impact = AssistanceImpact(h=HClass.H0, source="formal_parser")
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R3",
            calls=(
                CallRecord(
                    attempt_id=call_context.attempt_id or "att-placeholder",
                    response_ok=True,
                    usage=response.usage,
                ),
            ),
            candidates=tuple(candidates),
            verdicts=(
                Verdict(
                    kind="parse_ok", message="structured output parsed", assistance_impact=impact
                ),
            ),
            selection_rationale={
                "analysis": (
                    str(payload.get("analysis"))[:2000]
                    if payload.get("analysis") is not None
                    else ""
                ),
                "candidates_considered": len(candidates),
            },
            final_action=chosen,
            termination_reason="selected",
            assistance_impacts=(impact,),
        )

    @staticmethod
    def _parse_payload(raw: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OutputParseError("structured output is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise OutputParseError("structured output must be a JSON object")
        return cast(dict[str, Any], payload)


def cast_obs(observation: dict[Any, Any]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in observation.items():
        result[str(key)] = cast(JsonValue, value)
    return result
