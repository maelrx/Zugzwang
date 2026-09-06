"""Repair strategy (R2): formal feedback after parse/illegal failures.

Only formally permitted feedback is returned (legality_only default): the
model is told its action failed and, when the protocol exposes the legal
set, which actions were legal. Every retry is a new provider call recorded
in the trace; nothing is hidden.
"""

from __future__ import annotations

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

from ._prompt_hooks import append_retry_feedback
from .direct import build_observation_text


class RepairStrategy:
    """R2: DirectStrategy with formal feedback repair up to max_retries."""

    strategy_id = "chess.repair"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        max_retries: int = 1,
        feedback: str = "binary",
        retry_profile: str | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._feedback = retry_profile or (
            "binary_legality"
            if feedback in {"legality_only", "binary"}
            else "legality_reason"
            if feedback in {"reason_category", "legality_reason"}
            else "enumerate_after_failure"
            if feedback in {"enumerated", "constrained", "legal_actions"}
            else feedback
        )

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R2",
            declared_assistance_h=("H3" if self._feedback == "enumerate_after_failure" else "H2"),
            declared_assistance_k="K0",
            consumes_legal_actions=False,
            produces_candidates=False,
            max_model_calls=1 + self._max_retries,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        obs: dict[str, JsonValue] = (
            cast(dict[str, JsonValue], observation) if isinstance(observation, dict) else {}
        )
        base_prompt = build_observation_text(obs)
        base_prompt = append_retry_feedback(base_prompt, context)
        messages: list[Message] = [
            Message(role=MessageRole.USER, parts=(TextPart(text=base_prompt),))
        ]
        calls: list[CallRecord] = []
        verdicts: list[Verdict] = []
        impact = AssistanceImpact(
            h=(HClass.H3 if self._feedback == "enumerate_after_failure" else HClass.H1),
            source=(
                "legal_action_set"
                if self._feedback == "enumerate_after_failure"
                else "binary_legality"
            ),
        )

        for attempt_index in range(1 + self._max_retries):
            request = ModelRequest(
                model=context.model,
                messages=tuple(messages),
                output_constraint=OutputConstraint(format="text"),
                extensions={"chess.strategy": "repair", "attempt": attempt_index},
            )
            call_context = CallContext(
                run_id=context.run_id,
                episode_id=context.episode_id,
                step_id=context.step_id,
                fingerprint=f"chess-repair:{context.seed}:{attempt_index}",
            )
            try:
                result = await context.backend.infer(request, call_context)
            except Exception as exc:
                verdicts.append(
                    Verdict(kind="provider_error", message=getattr(exc, "stable_code", str(exc)))
                )
                break
            response = result.response
            raw = response.text().strip()
            calls.append(
                CallRecord(
                    attempt_id=call_context.attempt_id or "att-placeholder",
                    response_ok=True,
                    usage=response.usage,
                )
            )
            from ..codecs.uci import parse_uci

            move = None
            for token in raw.replace(",", " ").split():
                candidate = parse_uci(token, raise_on_invalid=False)
                if candidate is not None:
                    move = candidate.uci
                    break
            if move is None:
                verdicts.append(
                    Verdict(
                        kind="parse_error",
                        message=f"no UCI move found in output (attempt {attempt_index + 1})",
                    )
                )
                messages.append(
                    Message(
                        role=MessageRole.ASSISTANT,
                        parts=(TextPart(text=raw[:200]),),
                    )
                )
                messages.append(
                    Message(
                        role=MessageRole.USER,
                        parts=(
                            TextPart(
                                text=(
                                    "Your previous answer could not be parsed as a UCI move. "
                                    "Reply with exactly one move in UCI notation, e.g. e2e4."
                                )
                            ),
                        ),
                    )
                )
                continue

            legal_raw = obs.get("legal_actions")
            legal: list[Any] = (
                list(cast(list[Any], legal_raw)) if isinstance(legal_raw, list) else []
            )
            if legal and move not in {str(a) for a in legal}:
                verdicts.append(
                    Verdict(
                        kind="illegal",
                        message=f"move {move} is not in the legal set (attempt {attempt_index + 1})",
                    )
                )
                if attempt_index < self._max_retries:
                    if self._feedback == "enumerate_after_failure":
                        feedback_text = (
                            f"Move {move} is not legal in this position. "
                            f"Legal moves: {', '.join(str(a) for a in legal)}. "
                            "Reply with a legal UCI move."
                        )
                    elif self._feedback == "legality_reason":
                        feedback_text = (
                            f"Move {move} is not legal in this position. "
                            "Formal result: ILLEGAL. Reply with a different UCI move."
                        )
                    else:
                        feedback_text = (
                            f"Move {move} is not legal in this position. "
                            "The formal result was ILLEGAL. Reply with a different UCI move."
                        )
                    messages.append(
                        Message(
                            role=MessageRole.ASSISTANT,
                            parts=(TextPart(text=raw[:200]),),
                        )
                    )
                    messages.append(
                        Message(
                            role=MessageRole.USER,
                            parts=(TextPart(text=feedback_text),),
                        )
                    )
                    continue
                break

            verdicts.append(
                Verdict(kind="parse_ok", message="uci parsed", assistance_impact=impact)
            )
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R2",
                calls=tuple(calls),
                candidates=(Candidate(action=move, origin="repaired_output"),),
                verdicts=tuple(verdicts),
                final_action=move,
                termination_reason="selected",
                assistance_impacts=(impact,),
            )

        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R2",
            calls=tuple(calls),
            verdicts=tuple(verdicts),
            final_action=None,
            termination_reason="repair_exhausted",
            assistance_impacts=(impact,),
        )
