"""Reason-first / constrain-later strategy (GROUND-001 G4).

Phase 1: the model reasons freely WITHOUT the legal action set and proposes
candidate moves. Phase 2: the legal set is exposed and the model selects one
legal move, with its own phase-1 analysis carried as assistant context.

Assistance accounting: phase 1 = H0 (no grounding), phase 2 = H3
(legal_action_set). Candidates produced in phase 1 are recorded in the trace.
"""

from __future__ import annotations

import re
from typing import Any, cast

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

from ._image import build_message_parts
from ._knowledge import knowledge_impacts, render_knowledge_section
from ._prompt_hooks import append_retry_feedback, apply_prompt_override, apply_prompt_override_text
from .direct import build_observation_text
from .grounded import GroundedStrategy

_UCI_TOKEN = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b")

PHASE1_PROMPT = PromptProgram(
    template_id="chess.reason_then_ground.analyze",
    version="1.0.0",
    system_instructions=(
        "You are playing standard chess. Analyze the position freely: propose candidate "
        "moves and explain your reasoning. You do NOT yet have the legal move list. "
        "End with a line 'Candidates:' followed by UCI moves, one per line."
    ),
    strategy_stage="analyze",
)


class ReasonThenGroundStrategy:
    """G4: free reasoning first, legal grounding afterwards (2 calls)."""

    strategy_id = "chess.reason_then_ground"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, *, parse_json: bool = True) -> None:
        self._parse_json = parse_json
        self._grounded = GroundedStrategy(parse_json=parse_json)

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
            produces_candidates=True,
            max_model_calls=2,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        obs: dict[str, JsonValue] = (
            cast(dict[str, JsonValue], observation) if isinstance(observation, dict) else {}
        )
        legal_actions_raw = obs.get("legal_actions")
        legal_actions: list[Any] = (
            list(cast(list[Any], legal_actions_raw)) if isinstance(legal_actions_raw, list) else []
        )
        delayed_gateway = (
            context.legality_gateway
            if not legal_actions
            and context.capabilities.enumerate_actions
            and context.legality_gateway is not None
            else None
        )
        if not legal_actions and delayed_gateway is None:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R1",
                verdicts=(Verdict(kind="grounding_error", message="legal action set not exposed"),),
                final_action=None,
                termination_reason="grounding_error",
            )

        # Phase A gets a context with no gateway lease.  The legal set is only
        # requested after the free-reasoning provider call completes.
        phase1_context = context.model_copy(
            update={
                "legality_gateway": None,
                "capabilities": context.capabilities.model_copy(
                    update={"enumerate_actions": False}
                ),
            }
        )
        try:
            analysis, candidates, phase1_record = await self._phase1(obs, phase1_context)
        except _PhaseError as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R1",
                verdicts=(Verdict(kind="provider_error", message=str(exc)),),
                final_action=None,
                termination_reason="provider_error",
            )
        ground_obs = obs
        if delayed_gateway is not None:
            legal_set = delayed_gateway.enumerate_actions()
            legal_actions = list(legal_set.actions)
            ground_obs = dict(obs)
            legal_settings = obs.get("legal_actions")
            encoding_setting: Any = "uci"
            if isinstance(legal_settings, dict):
                encoding_setting = legal_settings.get("encoding", "uci")
            else:
                legality_config = context.config.get("legality")
                if isinstance(legality_config, dict):
                    encoding_setting = legality_config.get("encoding", "uci")
            encoding = str(encoding_setting)
            ground_obs["legal_actions"] = (
                list(range(len(legal_actions)))
                if encoding == "opaque_index"
                else [str(action) for action in legal_actions]
            )
            if encoding == "opaque_index":
                ground_obs["legal_actions_hash"] = legal_set.legal_hash
            if encoding == "san":
                ground_obs["legal_actions"] = [str(action) for action in legal_actions]
        phase2 = await self._phase2(ground_obs, legal_actions, analysis, context)
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R1",
            calls=(phase1_record, *phase2.calls),
            candidates=(*candidates, *phase2.candidates),
            verdicts=(
                Verdict(kind="analyze_ok", message="phase 1 produced candidates"),
                *phase2.verdicts,
            ),
            final_action=phase2.final_action,
            termination_reason=phase2.termination_reason,
            assistance_impacts=(
                AssistanceImpact(h=HClass.H0, source="free_reasoning_phase"),
                *knowledge_impacts(context.knowledge),
                AssistanceImpact(h=HClass.H3, source="legal_action_set"),
            ),
            selection_rationale=None,
        )

    async def _phase1(
        self,
        obs: dict[str, JsonValue],
        context: DecisionContext,
    ) -> tuple[str, tuple[Candidate, ...], CallRecord]:
        phase1_obs = dict(obs)
        for key in ("legal_actions", "legal_actions_uci", "legal_actions_hash"):
            phase1_obs.pop(key, None)
        text = build_observation_text(phase1_obs)
        knowledge_section = render_knowledge_section(context.knowledge)
        if knowledge_section:
            text = f"{text}\n\n{knowledge_section}"
        phase1_program = apply_prompt_override(PHASE1_PROMPT, context)
        prompt_text = phase1_program.render(text)
        prompt_text = append_retry_feedback(prompt_text, context)
        parts, required_capabilities = build_message_parts(
            phase1_obs, prompt_text, artifact_store=context.artifact_store
        )
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=parts),),
            output_constraint=OutputConstraint(format="text"),
            required_capabilities=required_capabilities,
            extensions={
                "chess.strategy": "reason_then_ground",
                "chess.phase": "analyze",
                "prompt_program": PHASE1_PROMPT.template_id,
            },
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-reason-then-ground-analyze:{context.seed}",
        )
        try:
            result = await context.backend.infer(request, call_context)
        except Exception as exc:
            raise _PhaseError(str(getattr(exc, "stable_code", exc))) from exc
        raw = result.response.text().strip()
        candidates = tuple(
            Candidate(action=move, origin="model_analysis")
            for move in dict.fromkeys(_UCI_TOKEN.findall(raw))
        )
        record = CallRecord(
            attempt_id=call_context.attempt_id or "att-placeholder",
            response_ok=True,
            usage=result.response.usage,
        )
        return raw, candidates, record

    async def _phase2(
        self,
        obs: dict[str, JsonValue],
        legal_actions: list[Any],
        analysis: str,
        context: DecisionContext,
    ) -> DecisionTrace:
        encoding = "index" if all(isinstance(a, int) for a in legal_actions) else "uci"
        if (
            encoding == "uci"
            and all(isinstance(a, str) for a in legal_actions)
            and not all(re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", str(a)) for a in legal_actions)
        ):
            encoding = "san"
        prompt = self._grounded.build_prompt(obs, encoding)
        knowledge_section = render_knowledge_section(context.knowledge)
        if knowledge_section:
            prompt = f"{prompt}\n\n{knowledge_section}"
        prompt = apply_prompt_override_text(prompt, context)
        prompt = append_retry_feedback(prompt, context)
        parts, required_capabilities = build_message_parts(
            obs, prompt, artifact_store=context.artifact_store
        )
        request = ModelRequest(
            model=context.model,
            messages=(
                Message(role=MessageRole.ASSISTANT, parts=(TextPart(text=analysis[:2000]),)),
                Message(role=MessageRole.USER, parts=parts),
            ),
            output_constraint=OutputConstraint(format="text"),
            required_capabilities=required_capabilities,
            extensions={"chess.strategy": "reason_then_ground", "chess.phase": "ground"},
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-reason-then-ground-ground:{context.seed}",
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
        raw = result.response.text().strip()
        try:
            action = self._grounded.resolve_action(raw, obs, legal_actions, encoding)
        except OutputParseError as exc:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R1",
                calls=(
                    CallRecord(
                        attempt_id=call_context.attempt_id or "att-placeholder",
                        response_ok=True,
                        usage=result.response.usage,
                    ),
                ),
                verdicts=(Verdict(kind="parse_error", message=exc.user_message),),
                final_action=None,
                termination_reason="parse_error",
            )
        impact = AssistanceImpact(h=HClass.H3, source="legal_action_set")
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R1",
            calls=(
                CallRecord(
                    attempt_id=call_context.attempt_id or "att-placeholder",
                    response_ok=True,
                    usage=result.response.usage,
                ),
            ),
            candidates=(Candidate(action=action, origin="grounded_model_output"),),
            verdicts=(
                Verdict(kind="parse_ok", message=f"{encoding} parsed", assistance_impact=impact),
            ),
            final_action=action,
            termination_reason="selected",
            assistance_impacts=(impact,),
        )


class _PhaseError(Exception):
    pass
