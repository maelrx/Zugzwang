"""Grounded strategy (R1): the environment's legal set is exposed.

The observation carries legal actions (UCI or opaque indices per the
observation policy). The model answers with one of them; the strategy
resolves opaque indices against the exposed ordered list.
"""

from __future__ import annotations

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
)
from zugzwang_core.ports.rules import ActionHandle
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
from ._prompt_hooks import append_retry_feedback, apply_prompt_override_text
from .direct import build_observation_text


class GroundedStrategy:
    """R1: state grounded with the legal action set."""

    strategy_id = "chess.grounded"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, *, parse_json: bool = True) -> None:
        self._parse_json = parse_json

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R1",
            declared_assistance_h="H3",
            declared_assistance_k="K0",
            consumes_legal_actions=True,
            produces_candidates=False,
            max_model_calls=1,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        obs: dict[str, JsonValue] = (
            cast(dict[str, JsonValue], observation) if isinstance(observation, dict) else {}
        )
        legal_actions_raw = obs.get("legal_actions")
        legal_actions: list[Any] = (
            list(cast(list[Any], legal_actions_raw)) if isinstance(legal_actions_raw, list) else []
        )
        if not legal_actions:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R1",
                verdicts=(Verdict(kind="grounding_error", message="legal action set not exposed"),),
                final_action=None,
                termination_reason="grounding_error",
            )
        knowledge_section = render_knowledge_section(context.knowledge)
        encoding = "index" if all(isinstance(a, int) for a in legal_actions) else "uci"
        if encoding == "uci" and all(isinstance(a, str) for a in legal_actions):
            import re

            if not all(re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", str(a)) for a in legal_actions):
                encoding = "san"
        prompt = self.build_prompt(obs, encoding)
        if knowledge_section:
            prompt = f"{prompt}\n\n{knowledge_section}"
        prompt = apply_prompt_override_text(prompt, context)
        prompt = append_retry_feedback(prompt, context)
        parts, required_capabilities = build_message_parts(
            obs, prompt, artifact_store=context.artifact_store
        )
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=parts),),
            output_constraint=OutputConstraint(format="text"),
            required_capabilities=required_capabilities,
            extensions={"chess.strategy": "grounded", "encoding": encoding},
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-grounded:{context.seed}",
        )
        try:
            result = await context.backend.infer(request, call_context)
        except Exception as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R1",
                verdicts=(
                    Verdict(kind="provider_error", message=getattr(exc, "stable_code", str(exc))),
                ),
                final_action=None,
                termination_reason="provider_error",
            )
        response = result.response
        raw = response.text().strip()
        impact = AssistanceImpact(h=HClass.H3, source="legal_action_set")
        impacts = (impact, *knowledge_impacts(context.knowledge))
        try:
            action = self.resolve_action(raw, obs, legal_actions, encoding)
        except OutputParseError as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R1",
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
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R1",
            calls=(
                CallRecord(
                    attempt_id=call_context.attempt_id or "att-placeholder",
                    response_ok=True,
                    usage=response.usage,
                ),
            ),
            candidates=(Candidate(action=action, origin="grounded_model_output"),),
            verdicts=(
                Verdict(kind="parse_ok", message=f"{encoding} parsed", assistance_impact=impact),
            ),
            final_action=action,
            termination_reason="selected",
            assistance_impacts=impacts,
        )

    def resolve_action(
        self, raw: str, obs: dict[str, JsonValue], legal_actions: list[Any], encoding: str
    ) -> Any:
        if encoding == "index":
            try:
                index = int(raw)
            except ValueError as exc:
                raise OutputParseError(
                    f"expected an index into the legal move list, got {raw!r}"
                ) from exc
            if not 0 <= index < len(legal_actions):
                raise OutputParseError(f"index {index} out of range (0..{len(legal_actions) - 1})")
            return ActionHandle(
                index=index,
                ordering_hash=str(obs.get("legal_actions_hash") or ""),
            )
        if encoding == "san":
            legal_san = {str(a).strip().rstrip("+#") for a in legal_actions}
            parallel_uci = cast(list[Any], obs.get("legal_actions_uci") or [])
            for token in raw.replace(",", " ").split():
                candidate = token.strip().rstrip("+#")
                if candidate in legal_san:
                    index = next(
                        (
                            i
                            for i, a in enumerate(legal_actions)
                            if str(a).strip().rstrip("+#") == candidate
                        ),
                        -1,
                    )
                    if 0 <= index < len(parallel_uci):
                        return str(parallel_uci[index])
                    return candidate
            raise OutputParseError(f"no legal SAN move found in {raw[:120]!r}")
        from ..codecs.uci import parse_uci

        for token in raw.replace(",", " ").split():
            move = parse_uci(token, raise_on_invalid=False)
            if move is not None and move.uci in {str(a) for a in legal_actions}:
                return move.uci
        raise OutputParseError(f"no legal UCI move found in {raw[:120]!r}")

    def build_prompt(self, obs: dict[str, JsonValue], encoding: str) -> str:
        base = build_observation_text(obs)
        legal_raw = obs.get("legal_actions")
        legal: list[Any] = (
            [v for v in cast(list[Any], legal_raw) if isinstance(v, (str, int))]
            if isinstance(legal_raw, list)
            else []
        )
        lines = [base]
        if encoding == "index":
            listing = "\n".join(f"{i}: {move}" for i, move in enumerate(legal))
            lines.append("Legal moves (reply with the index only):")
            lines.append(listing)
        else:
            lines.append("Legal moves: " + ", ".join(str(m) for m in legal))
            lines.append("Reply with one legal move in UCI notation.")
        return "\n".join(lines)
