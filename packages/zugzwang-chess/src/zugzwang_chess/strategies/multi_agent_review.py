"""R5 multi-agent review chain for one chess decision.

The chain is deliberately explicit: a critical scout maps the position, a
strategic planner consumes that report, and a final reviewer selects one UCI
action. All three are ordinary model calls through the configured backend.
RulesKernel validation remains outside this strategy in the coordinator.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, cast

from zugzwang_chess.strategies._calls import new_call_attempt_id
from zugzwang_core.domain.assistance import AssistanceImpact, HClass, KClass
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.domain.money import TokenUsage
from zugzwang_core.ports.model import (
    CallContext,
    Capability,
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

from ..codecs.uci import parse_uci
from ._prompt_hooks import append_retry_feedback, apply_prompt_override_text
from .direct import build_observation_text

_UCI_TOKEN = re.compile(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b")
_MAX_REPORT_CHARS = 6000
_ROLE_ORDER = ("critical_scout", "strategy_planner", "final_reviewer")

_SCOUT_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "critical_map": {"type": "string"},
        "hanging_pieces": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "piece": {"type": "string"},
                    "square": {"type": "string"},
                    "reason": {"type": "string"},
                    "severity": {"type": "string"},
                },
                "required": ["piece", "square", "reason", "severity"],
                "additionalProperties": False,
            },
        },
        "tactical_ideas": {"type": "array", "items": {"type": "string"}},
        "candidate_moves": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": [
        "critical_map",
        "hanging_pieces",
        "tactical_ideas",
        "candidate_moves",
        "confidence",
    ],
    "additionalProperties": False,
}

_PLANNER_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "plan": {"type": "string"},
        "candidate_moves": {"type": "array", "items": {"type": "string"}},
        "preferred_move": {"type": "string"},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["plan", "candidate_moves", "preferred_move", "risks"],
    "additionalProperties": False,
}

_REVIEW_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "move": {"type": "string"},
        "review": {"type": "string"},
        "critical_risks_addressed": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["move", "review", "critical_risks_addressed", "confidence"],
    "additionalProperties": False,
}


class MultiAgentReviewStrategy:
    """R5: scout -> planner -> final reviewer for one model decision."""

    strategy_id = "chess.multi_agent_review"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R5",
            declared_assistance_h="H2",
            declared_assistance_k="K0",
            consumes_legal_actions=False,
            produces_candidates=True,
            max_model_calls=3,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        obs = _as_observation(observation)
        position = _position_text(obs)
        critical, critical_raw, critical_call = await self._ask(
            role="critical-scout",
            schema=_SCOUT_SCHEMA,
            prompt=self._scout_prompt(position),
            context=context,
        )
        planner, planner_raw, planner_call = await self._ask(
            role="strategy-planner",
            schema=_PLANNER_SCHEMA,
            prompt=self._planner_prompt(position, critical, critical_raw),
            context=context,
        )
        reviewer, reviewer_raw, reviewer_call = await self._ask(
            role="final-reviewer",
            schema=_REVIEW_SCHEMA,
            prompt=self._reviewer_prompt(position, critical, planner, critical_raw, planner_raw),
            context=context,
        )

        calls = (critical_call, planner_call, reviewer_call)
        candidates = _candidates(critical, planner)
        move = _extract_move(reviewer, reviewer_raw)
        if move is not None and all(candidate.action != move for candidate in candidates):
            candidates = (*candidates, Candidate(action=move, origin="final_reviewer"))

        verdicts = (
            _call_verdict("critical_scout", critical_call),
            _call_verdict("strategy_planner", planner_call),
            _call_verdict("final_reviewer", reviewer_call),
        )
        impact = AssistanceImpact(
            h=HClass.H0,
            k=KClass.K0,
            source="multi_agent_model_review",
        )
        rationale: dict[str, JsonValue] = {
            "workflow": list(_ROLE_ORDER),
            "critical_scout": cast(JsonValue, critical),
            "strategy_planner": cast(JsonValue, planner),
            "final_reviewer": cast(JsonValue, reviewer),
            "model_only": True,
            "engine_used": False,
            "legal_actions_exposed": False,
        }
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R5",
            calls=calls,
            candidates=candidates,
            verdicts=(*verdicts, Verdict(kind="final_action_parsed" if move else "parse_error")),
            selection_rationale=rationale,
            final_action=move,
            termination_reason="selected" if move else "parse_error",
            assistance_impacts=(impact,),
        )

    async def _ask(
        self,
        *,
        role: str,
        schema: dict[str, JsonValue],
        prompt: str,
        context: DecisionContext,
    ) -> tuple[dict[str, Any], str, CallRecord]:
        prompt = apply_prompt_override_text(append_retry_feedback(prompt, context), context)
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text=prompt),)),),
            output_constraint=OutputConstraint.model_validate(
                {"format": "json_schema", "schema": schema}
            ),
            required_capabilities=frozenset({Capability.JSON_SCHEMA_OUTPUT}),
            extensions={
                "chess.strategy": "multi_agent_review",
                "chess.agent_role": role,
            },
            metadata={"agent_role": role, "workflow": "critical-scout-planner-reviewer"},
        )
        before = _recorded_attempt_ids(context.backend)
        call_context = CallContext(
            attempt_id=new_call_attempt_id(),
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-multi-agent:{role}:{context.seed}",
            metadata={"agent_role": role},
        )
        try:
            result = await context.backend.infer(request, call_context)
        except Exception as exc:
            attempt_id = _latest_attempt_id(context.backend, before, role)
            code = str(getattr(exc, "stable_code", type(exc).__name__))
            return (
                {"error": code},
                "",
                CallRecord(
                    attempt_id=attempt_id,
                    request_fingerprint=call_context.fingerprint,
                    response_ok=False,
                    usage=TokenUsage(),
                    failure_code=code,
                ),
            )
        raw = result.response.text().strip()
        report = _parse_report(raw)
        attempt_id = _latest_attempt_id(context.backend, before, role)
        return (
            report,
            raw,
            CallRecord(
                attempt_id=attempt_id,
                request_fingerprint=call_context.fingerprint,
                response_ok=True,
                usage=result.response.usage,
                cost=result.response.cost,
            ),
        )

    @staticmethod
    def _scout_prompt(position: str) -> str:
        return (
            "You are the Critical Scout in a model-only chess review chain.\n"
            "Map the complete current position from the supplied observation. Focus on "
            "checks, captures, threats, hanging or overloaded pieces, king safety and "
            "tactical forcing ideas. Do not use Stockfish, tablebases, opening books, "
            "legal-action lists, evaluation artifacts or outside knowledge. This is a "
            "structured assessment, not private chain-of-thought. Return JSON only.\n\n"
            f"{position}\n\n"
            "Schema intent: critical_map, hanging_pieces, tactical_ideas, candidate_moves, confidence."
        )

    @staticmethod
    def _planner_prompt(position: str, critical: dict[str, Any], critical_raw: str) -> str:
        report = _report_text(critical, critical_raw)
        return (
            "You are the Strategic Planner. Re-check the position yourself, then use the "
            "Critical Scout report as fallible model-generated input. Select a practical "
            "plan and a short list of candidate UCI moves. Do not use an engine, legal "
            "move list, tablebase, opening book or external knowledge. Do not reveal or "
            "claim private chain-of-thought. Return JSON only.\n\n"
            f"POSITION\n{position}\n\nCRITICAL SCOUT REPORT\n{report}\n\n"
            "Schema intent: plan, candidate_moves, preferred_move, risks."
        )

    @staticmethod
    def _reviewer_prompt(
        position: str,
        critical: dict[str, Any],
        planner: dict[str, Any],
        critical_raw: str,
        planner_raw: str,
    ) -> str:
        critical_text = _report_text(critical, critical_raw)
        planner_text = _report_text(planner, planner_raw)
        return (
            "You are the Final Reviewer. Audit the proposed plan against the exact current "
            "position and the tactical map. Reject unsupported ideas, check that the final "
            "choice is a plausible UCI move, and return exactly one recommended move. "
            "This remains model-only: no Stockfish, tablebases, legal-action list, "
            "evaluation artifact or external knowledge. Do not claim private chain-of-thought. "
            "Return JSON only.\n\n"
            f"POSITION\n{position}\n\nCRITICAL SCOUT\n{critical_text}\n\n"
            f"STRATEGIC PLAN\n{planner_text}\n\n"
            "Schema intent: move, review, critical_risks_addressed, confidence."
        )


def _as_observation(observation: Any) -> dict[str, JsonValue]:
    if not isinstance(observation, Mapping):
        return {}
    mapping = cast(Mapping[Any, Any], observation)
    return {str(key): cast(JsonValue, value) for key, value in mapping.items()}


def _position_text(observation: dict[str, JsonValue]) -> str:
    rendered = build_observation_text(observation)
    return rendered.removesuffix("\nReply with a single move in UCI notation (e.g. e2e4).")


def _parse_report(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return cast(dict[str, Any], payload)
    return {"unparsed": text[:_MAX_REPORT_CHARS]} if text else {}


def _report_text(report: dict[str, Any], raw: str) -> str:
    payload: Any = report if report else {"unparsed": raw}
    try:
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        rendered = raw
    return rendered[:_MAX_REPORT_CHARS]


def _extract_move(report: dict[str, Any], raw: str) -> str | None:
    explicit_field = False
    for key in ("move", "chosen_move", "preferred_move", "recommended_move"):
        value = report.get(key)
        if isinstance(value, str):
            explicit_field = True
            parsed = _parse_model_move(value)
            if parsed is not None:
                return parsed.uci
    if explicit_field:
        return None
    for token in _UCI_TOKEN.findall(raw):
        parsed = _parse_model_move(token)
        if parsed is not None:
            return parsed.uci
    return None


def _parse_model_move(value: str) -> Any | None:
    """Parse strict UCI plus explicit coordinate notation such as ``Ng1f3``."""
    text = value.strip()
    parsed = parse_uci(text, raise_on_invalid=False)
    if parsed is not None:
        return parsed
    if re.fullmatch(r"[KQRBN][a-h][1-8][a-h][1-8][qrbn]?", text):
        return parse_uci(text[1:], raise_on_invalid=False)
    return None


def _candidates(critical: dict[str, Any], planner: dict[str, Any]) -> tuple[Candidate, ...]:
    result: list[Candidate] = []
    seen: set[str] = set()
    reports: tuple[tuple[str, dict[str, Any]], ...] = (
        ("critical_scout", critical),
        ("strategy_planner", planner),
    )
    for source, report in reports:
        values: Any = report.get("candidate_moves")
        if not isinstance(values, list):
            continue
        for value in cast(list[Any], values):
            if not isinstance(value, str):
                continue
            parsed = _parse_model_move(value)
            if parsed is None or parsed.uci in seen:
                continue
            seen.add(parsed.uci)
            result.append(Candidate(action=parsed.uci, origin=source))
    return tuple(result)


def _call_verdict(role: str, call: CallRecord) -> Verdict:
    return Verdict(
        kind=f"{role}.completed" if call.response_ok else f"{role}.failed",
        message=call.failure_code or "provider response recorded",
    )


def _recorded_attempt_ids(backend: Any) -> tuple[str, ...]:
    getter = getattr(backend, "evidence_for_current_decision", None)
    if not callable(getter):
        return ()
    value = getter()
    if not isinstance(value, Mapping):
        return ()
    mapping = cast(Mapping[Any, Any], value)
    return tuple(str(key) for key in mapping)


def _latest_attempt_id(backend: Any, before: tuple[str, ...], role: str) -> str:
    after = _recorded_attempt_ids(backend)
    new_ids = [attempt_id for attempt_id in after if attempt_id not in before]
    return new_ids[-1] if new_ids else f"att-multi-agent-{role}"
