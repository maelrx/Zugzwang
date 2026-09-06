"""R7 legal-action tree with an explicit memory ablation.

Formal affordances are visible to every role. Hypothetical branches are
created only through the runtime SearchWorkspace, never by mutating the
canonical game state.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, cast

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
from .direct import build_observation_text

_UCI_TOKEN = re.compile(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b")
_MAX_REPORT_CHARS = 6000
_ROLE_ORDER = ("position_mapper", "variant_analyst", "final_reviewer")

_MAPPER_SCHEMA: dict[str, JsonValue] = {
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
        "illegal_probes": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": [
        "critical_map",
        "hanging_pieces",
        "tactical_ideas",
        "candidate_moves",
        "illegal_probes",
        "confidence",
    ],
    "additionalProperties": False,
}

_VARIANT_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "root_move": {"type": "string"},
                    "reply_move": {"type": "string"},
                    "assessment": {"type": "string"},
                    "risks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["root_move", "reply_move", "assessment", "risks"],
                "additionalProperties": False,
            },
        },
        "preferred_root": {"type": "string"},
    },
    "required": ["variants", "preferred_root"],
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


class LegalTreeMemoryStrategy:
    """R7: legal root set, model branches and retrieved memory."""

    strategy_id = "chess.legal_tree_memory"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, *, memory_mode: str = "episodic") -> None:
        if memory_mode not in {"episodic", "persistent"}:
            raise ValueError(f"unknown search memory mode {memory_mode!r}")
        self._memory_mode = memory_mode

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R7",
            declared_assistance_h="H4",
            declared_assistance_k="K6" if self._memory_mode == "persistent" else "K0",
            consumes_legal_actions=True,
            produces_candidates=True,
            max_model_calls=3,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        mode = _memory_mode(context, self._memory_mode)
        if context.legality_gateway is None:
            return self._error("legality_gateway_missing", mode)
        if context.search_workspace is None:
            return self._error("search_workspace_missing", mode)
        legal_set = context.legality_gateway.enumerate_actions()
        legal_moves = tuple(str(action) for action in legal_set.actions)
        legal_context: dict[str, JsonValue] = {
            "count": len(legal_moves),
            "hash": str(legal_set.legal_hash),
            "moves": list(legal_moves),
        }
        retrieved = _retrieve_memory(
            context.search_memory,
            context.search_workspace,
            mode,
        )
        position = build_observation_text(_as_observation(observation))
        affordances = _affordance_text(legal_context, mode, retrieved)
        calls: list[CallRecord] = []
        verdicts: list[Verdict] = []

        mapper, mapper_raw, mapper_call = await self._ask(
            role="position-mapper",
            schema=_MAPPER_SCHEMA,
            prompt=self._mapper_prompt(position, affordances),
            context=context,
        )
        calls.append(mapper_call)
        verdicts.append(_call_verdict("position_mapper", mapper_call))

        root_moves = _move_values(mapper.get("candidate_moves"))
        illegal_probes = _move_values(mapper.get("illegal_probes"))
        root_branches, branch_summaries = self._materialize_roots(
            root_moves=root_moves,
            illegal_probes=illegal_probes,
            context=context,
            verdicts=verdicts,
        )
        if not root_branches:
            return self._trace(
                calls=calls,
                verdicts=(*verdicts, Verdict(kind="no_legal_branch")),
                candidates=tuple(
                    Candidate(action=move, origin="position_mapper") for move in _unique(root_moves)
                ),
                rationale=cast(
                    dict[str, JsonValue],
                    {
                        "workflow": list(_ROLE_ORDER),
                        "memory_mode": mode,
                        "legal_action_set": legal_context,
                        "illegal_probes": illegal_probes,
                        "root_branches": branch_summaries,
                        "variant_branches": [],
                        "retrieved_memory": retrieved,
                    },
                ),
                final_action=None,
                mode=mode,
                reason="no_legal_branch",
            )

        variant, _variant_raw, variant_call = await self._ask(
            role="variant-analyst",
            schema=_VARIANT_SCHEMA,
            prompt=self._variant_prompt(
                position,
                affordances,
                branch_summaries,
                mapper,
                mapper_raw,
            ),
            context=context,
        )
        calls.append(variant_call)
        verdicts.append(_call_verdict("variant_analyst", variant_call))
        variant_records = self._materialize_variants(
            variant=variant,
            root_branches=root_branches,
            context=context,
            verdicts=verdicts,
        )

        reviewer, reviewer_raw, reviewer_call = await self._ask(
            role="final-reviewer",
            schema=_REVIEW_SCHEMA,
            prompt=self._reviewer_prompt(
                position,
                affordances,
                branch_summaries,
                variant_records,
                mapper,
                variant,
            ),
            context=context,
        )
        calls.append(reviewer_call)
        verdicts.append(_call_verdict("final_reviewer", reviewer_call))
        final_action = _parse_move(reviewer.get("move")) or _first_uci(reviewer_raw)
        final_validation = None
        if final_action is not None:
            checked = context.legality_gateway.validate(final_action)
            final_validation = {
                "action": final_action,
                "legal": bool(checked.legal),
                "reason": checked.reason,
            }
            if not checked.legal:
                verdicts.append(
                    Verdict(
                        kind="final_action_illegal",
                        message=f"{final_action}: {checked.reason or 'illegal'}",
                    )
                )

        rationale: dict[str, JsonValue] = {
            "workflow": list(_ROLE_ORDER),
            "position_mapper": cast(JsonValue, mapper),
            "variant_analyst": cast(JsonValue, variant),
            "final_reviewer": cast(JsonValue, reviewer),
            "memory_mode": mode,
            "legal_action_set": legal_context,
            "illegal_probes": cast(JsonValue, illegal_probes),
            "root_branches": cast(JsonValue, branch_summaries),
            "retrieved_memory": cast(JsonValue, retrieved),
            "variant_branches": cast(JsonValue, variant_records),
            "final_validation": cast(JsonValue, final_validation),
            "model_only": True,
            "engine_used": False,
        }
        return self._trace(
            calls=calls,
            verdicts=(
                *verdicts,
                Verdict(kind="final_action_parsed" if final_action else "parse_error"),
            ),
            candidates=tuple(
                Candidate(action=move, origin="position_mapper") for move in root_branches
            ),
            rationale=rationale,
            final_action=final_action,
            mode=mode,
            reason="selected" if final_action else "parse_error",
        )

    def _materialize_roots(
        self,
        *,
        root_moves: list[str],
        illegal_probes: list[str],
        context: DecisionContext,
        verdicts: list[Verdict],
    ) -> tuple[dict[str, str], list[dict[str, JsonValue]]]:
        workspace = context.search_workspace
        memory = context.search_memory
        root_branches: dict[str, str] = {}
        summaries: list[dict[str, JsonValue]] = []
        max_roots = _search_int(context, "max_root_branches", 4)
        for move in _unique(root_moves + illegal_probes):
            if len(root_branches) >= max_roots and move not in illegal_probes:
                continue
            result = workspace.try_move(
                workspace.root_id,
                move,
                created_by="position-mapper:model",
            )
            if result.get("legal") and result.get("child_node_id"):
                child_id = str(result["child_node_id"])
                root_branches[move] = child_id
                child_state = workspace.state(child_id)
                reply_gateway = context.legality_gateway.bind_state(child_state)
                reply_set = reply_gateway.enumerate_actions()
                summaries.append(
                    {
                        "root_move": move,
                        "node_id": child_id,
                        "fen": str(getattr(child_state, "fen", "")),
                        "terminal": bool(result.get("terminal")),
                        "legal_reply_count": len(reply_set.actions),
                        "legal_reply_hash": str(reply_set.legal_hash),
                        "legal_reply_moves": [str(action) for action in reply_set.actions],
                    }
                )
                _record_memory(
                    memory,
                    node_id=child_id,
                    kind="candidate",
                    content=f"model candidate root {move}",
                    generated_by=str(context.model),
                    verdicts=verdicts,
                )
            else:
                verdicts.append(
                    Verdict(
                        kind="illegal_probe_rejected",
                        message=f"{move}: {result.get('reason', 'illegal')}",
                    )
                )
        return root_branches, summaries

    def _materialize_variants(
        self,
        *,
        variant: dict[str, Any],
        root_branches: dict[str, str],
        context: DecisionContext,
        verdicts: list[Verdict],
    ) -> list[dict[str, JsonValue]]:
        workspace = context.search_workspace
        memory = context.search_memory
        records: list[dict[str, JsonValue]] = []
        raw_variants = variant.get("variants")
        if not isinstance(raw_variants, list):
            return records
        for raw in cast(list[Any], raw_variants):
            if not isinstance(raw, Mapping):
                continue
            raw_data = cast(Mapping[str, Any], raw)
            root = _parse_move(raw_data.get("root_move"))
            reply = _parse_move(raw_data.get("reply_move"))
            if root is None or reply is None or root not in root_branches:
                verdicts.append(Verdict(kind="variant_unparsed", message="root or reply missing"))
                continue
            result = workspace.try_move(
                root_branches[root],
                reply,
                created_by="variant-analyst:model",
            )
            record: dict[str, JsonValue] = {
                "root_move": root,
                "reply_move": reply,
                "legal": bool(result.get("legal")),
                "child_node_id": (
                    str(result["child_node_id"]) if result.get("child_node_id") else None
                ),
                "assessment": str(raw_data.get("assessment", ""))[:1000],
                "risks": [
                    str(item)[:500]
                    for item in cast(list[Any], raw_data.get("risks", []))
                    if isinstance(item, str)
                ],
            }
            if result.get("legal") and result.get("child_node_id"):
                _record_memory(
                    memory,
                    node_id=str(result["child_node_id"]),
                    kind="refutation",
                    content=f"model variant {root} reply {reply}",
                    generated_by=str(context.model),
                    verdicts=verdicts,
                )
            else:
                record["reason"] = str(result.get("reason", "illegal"))
                verdicts.append(
                    Verdict(kind="variant_reply_rejected", message=f"{root} -> {reply}")
                )
            records.append(record)
        return records

    async def _ask(
        self,
        *,
        role: str,
        schema: dict[str, JsonValue],
        prompt: str,
        context: DecisionContext,
    ) -> tuple[dict[str, Any], str, CallRecord]:
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text=prompt),)),),
            output_constraint=OutputConstraint.model_validate(
                {"format": "json_schema", "schema": schema}
            ),
            required_capabilities=frozenset({Capability.JSON_SCHEMA_OUTPUT}),
            extensions={
                "chess.strategy": "legal_tree_memory",
                "chess.agent_role": role,
            },
            metadata={"agent_role": role, "workflow": "mapper-variant-reviewer"},
        )
        before = _recorded_attempt_ids(context.backend)
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-legal-tree-memory:{role}:{context.seed}",
            metadata={"agent_role": role},
        )
        try:
            result = await context.backend.infer(request, call_context)
        except Exception as exc:
            code = str(getattr(exc, "stable_code", type(exc).__name__))
            return (
                {"error": code},
                "",
                CallRecord(
                    attempt_id=_latest_attempt_id(context.backend, before, role),
                    request_fingerprint=call_context.fingerprint,
                    response_ok=False,
                    usage=TokenUsage(),
                    failure_code=code,
                ),
            )
        raw = result.response.text().strip()
        return (
            _parse_report(raw),
            raw,
            CallRecord(
                attempt_id=_latest_attempt_id(context.backend, before, role),
                request_fingerprint=call_context.fingerprint,
                response_ok=True,
                usage=result.response.usage,
                cost=result.response.cost,
            ),
        )

    @staticmethod
    def _mapper_prompt(position: str, affordances: str) -> str:
        return (
            "You are the Position Mapper in a chess research agent. Inspect checks, "
            "captures, threats, king safety and overloaded or hanging pieces. The formal "
            "rules gateway has supplied the complete finite root-action set below. Use it "
            "to select candidates. You may list a small number of intentionally invalid "
            "UCI probes for the RulesKernel to reject; do not claim that all illegal "
            "strings can be enumerated. Do not use Stockfish, tablebases or external "
            "evaluation. Return JSON only.\n\n"
            f"POSITION\n{position}\n\n{affordances}\n\n"
            "Schema: critical_map, hanging_pieces, tactical_ideas, candidate_moves, "
            "illegal_probes, confidence."
        )

    @staticmethod
    def _variant_prompt(
        position: str,
        affordances: str,
        branches: list[dict[str, JsonValue]],
        mapper: dict[str, Any],
        mapper_raw: str,
    ) -> str:
        return (
            "You are the Variant Analyst. Re-check the position and the mapper as fallible "
            "input. Compare the formal branches below and propose at most one concrete "
            "reply move for each root candidate. The RulesKernel will validate replies. "
            "The legal root list and retrieved memory are available to you. Do not use "
            "Stockfish, tablebases or external evaluation. Return JSON only.\n\n"
            f"POSITION\n{position}\n\n{affordances}\n\n"
            f"ROOT BRANCHES\n{json.dumps(branches, ensure_ascii=False)}\n\n"
            f"MAPPER REPORT\n{_report_text(mapper, mapper_raw)}\n\n"
            "Schema: variants[{root_move, reply_move, assessment, risks}], preferred_root."
        )

    @staticmethod
    def _reviewer_prompt(
        position: str,
        affordances: str,
        branches: list[dict[str, JsonValue]],
        variants: list[dict[str, JsonValue]],
        mapper: dict[str, Any],
        variant: dict[str, Any],
    ) -> str:
        return (
            "You are the Final Reviewer. Choose exactly one root move from the formal legal "
            "root-action set. Audit checks, captures, king safety, branch replies and "
            "retrieved memory. Reject a locally attractive move if it permits a forcing "
            "reply or immediate mate. The final answer must be one UCI root move. Do not "
            "use Stockfish, tablebases or external evaluation. Return JSON only.\n\n"
            f"POSITION\n{position}\n\n{affordances}\n\n"
            f"ROOT BRANCHES\n{json.dumps(branches, ensure_ascii=False)}\n\n"
            f"VARIANT RESULTS\n{json.dumps(variants, ensure_ascii=False)}\n\n"
            f"MAPPER\n{_report_text(mapper, '')}\n\n"
            f"VARIANT ANALYST\n{_report_text(variant, '')}\n\n"
            "Schema: move, review, critical_risks_addressed, confidence."
        )

    def _trace(
        self,
        *,
        calls: list[CallRecord],
        verdicts: tuple[Verdict, ...],
        candidates: tuple[Candidate, ...],
        rationale: dict[str, JsonValue],
        final_action: str | None,
        mode: str,
        reason: str,
    ) -> DecisionTrace:
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R7",
            calls=tuple(calls),
            candidates=candidates,
            verdicts=verdicts,
            selection_rationale=rationale,
            final_action=final_action,
            termination_reason=reason,
            assistance_impacts=(
                AssistanceImpact(
                    h=HClass.H4,
                    k=KClass.K6 if mode == "persistent" else KClass.K0,
                    source="legal_tree_memory",
                ),
            ),
        )

    def _error(self, reason: str, mode: str) -> DecisionTrace:
        return self._trace(
            calls=[],
            verdicts=(Verdict(kind="configuration_error", message=reason),),
            candidates=(),
            rationale={
                "workflow": list(_ROLE_ORDER),
                "memory_mode": mode,
                "legal_actions_exposed": False,
            },
            final_action=None,
            mode=mode,
            reason=reason,
        )


def _as_observation(observation: Any) -> dict[str, JsonValue]:
    if not isinstance(observation, Mapping):
        return {}
    return {
        str(key): cast(JsonValue, value)
        for key, value in cast(Mapping[Any, Any], observation).items()
    }


def _memory_mode(context: DecisionContext, default: str) -> str:
    search = context.config.get("search")
    if isinstance(search, Mapping):
        value = str(search.get("memory_mode", default))
        if value in {"episodic", "persistent"}:
            return value
    return default


def _search_int(context: DecisionContext, name: str, default: int) -> int:
    search = context.config.get("search")
    if isinstance(search, Mapping):
        value = search.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return max(1, value)
    return default


def _affordance_text(
    legal_context: dict[str, JsonValue],
    mode: str,
    retrieved: list[dict[str, JsonValue]],
) -> str:
    moves = cast(list[Any], legal_context["moves"])
    return (
        "LEGAL ROOT MOVES (complete finite set from RulesKernel; H3)\n"
        f"Count: {legal_context['count']}\n"
        f"Hash: {legal_context['hash']}\n"
        f"Moves: {', '.join(str(move) for move in moves)}\n"
        f"MEMORY MODE: {mode}\n"
        f"RETRIEVED MEMORY: {json.dumps(retrieved, ensure_ascii=False)}"
    )


def _retrieve_memory(memory: Any, workspace: Any, mode: str) -> list[dict[str, JsonValue]]:
    if memory is None:
        return []
    results: list[dict[str, JsonValue]] = []
    for retriever in (
        "exact_state",
        "ancestors",
        "siblings",
        "root_move",
        "refutation",
        "failure",
        "frontier",
        "disagreement",
        "transposition",
    ):
        try:
            result = memory.retrieve(
                retriever,
                workspace.root_id,
                _RetrievalBudget(max_items=4),
            )
        except (KeyError, ValueError):
            continue
        for item in result.items:
            results.append(
                {
                    "retriever": result.retriever,
                    "memory_id": item.memory_id,
                    "kind": item.kind,
                    "content": item.content[:1000],
                    "source_node_ids": list(item.source_node_ids),
                    "generated_by": item.generated_by,
                    "mode": mode,
                }
            )
    return results


def _record_memory(
    memory: Any,
    *,
    node_id: str,
    kind: str,
    content: str,
    generated_by: str,
    verdicts: list[Verdict],
) -> None:
    if memory is None:
        return
    try:
        memory.record(
            node_id=node_id,
            kind=kind,
            content=content,
            generated_by=generated_by,
        )
    except Exception as exc:
        verdicts.append(Verdict(kind="memory_record_rejected", message=str(exc)[:160]))


def _move_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    moves: list[str] = []
    for item in cast(list[Any], value):
        parsed = _parse_move(item)
        if parsed is not None:
            moves.append(parsed)
    return moves


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _parse_move(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = parse_uci(value.strip(), raise_on_invalid=False)
    return parsed.uci if parsed is not None else None


def _first_uci(raw: str) -> str | None:
    match = _UCI_TOKEN.search(raw)
    return match.group(0) if match else None


def _parse_report(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = re.sub(
            r"^" + fence + r"(?:json)?\s*|\s*" + fence + r"$",
            "",
            text,
            flags=re.IGNORECASE,
        )
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
    return tuple(str(key) for key in cast(Mapping[Any, Any], value))


def _latest_attempt_id(backend: Any, before: tuple[str, ...], role: str) -> str:
    after = _recorded_attempt_ids(backend)
    new_ids = [attempt_id for attempt_id in after if attempt_id not in before]
    return new_ids[-1] if new_ids else f"att-legal-tree-memory-{role}"


class _RetrievalBudget:
    def __init__(self, *, max_items: int) -> None:
        self.max_items = max_items
