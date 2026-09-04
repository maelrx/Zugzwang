"""R7 single-agent tree strategy with a controlled hypothesis surface.

One model call performs the position scan, candidate generation, variant
proposal and final selection. The runtime supplies formal legal affordances,
the strategy records model-proposed illegal probes, and SearchWorkspace owns
all hypothetical transitions.
"""

from __future__ import annotations

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

from ._prompt_hooks import append_retry_feedback, apply_prompt_override_text
from .direct import build_observation_text
from .legal_tree_memory import (
    tree_affordance_text,
    tree_as_observation,
    tree_call_verdict,
    tree_first_uci,
    tree_latest_attempt_id,
    tree_memory_mode,
    tree_move_values,
    tree_parse_move,
    tree_parse_report,
    tree_record_memory,
    tree_recorded_attempt_ids,
    tree_retrieve_memory,
    tree_search_int,
    tree_unique,
)

_ROLE = "single-agent"
_STRATEGY_NAME = "single_agent_tree"
_HANGING_PIECE_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "piece": {"type": "string"},
        "square": {"type": "string"},
        "reason": {"type": "string"},
        "severity": {"type": "string"},
    },
    "required": ["piece", "square", "reason", "severity"],
    "additionalProperties": False,
}
_VARIANT_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "root_move": {"type": "string"},
        "reply_move": {"type": "string"},
        "illegal_reply_probes": {"type": "array", "items": {"type": "string"}},
        "assessment": {"type": "string"},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "root_move",
        "reply_move",
        "illegal_reply_probes",
        "assessment",
        "risks",
    ],
    "additionalProperties": False,
}
_REPORT_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "critical_map": {"type": "string"},
        "hanging_pieces": {"type": "array", "items": _HANGING_PIECE_SCHEMA},
        "tactical_ideas": {"type": "array", "items": {"type": "string"}},
        "candidate_moves": {"type": "array", "items": {"type": "string"}},
        "illegal_probes": {"type": "array", "items": {"type": "string"}},
        "variants": {"type": "array", "items": _VARIANT_SCHEMA},
        "move": {"type": "string"},
        "analysis": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": [
        "critical_map",
        "hanging_pieces",
        "tactical_ideas",
        "candidate_moves",
        "illegal_probes",
        "variants",
        "move",
        "analysis",
        "confidence",
    ],
    "additionalProperties": False,
}


class SingleAgentTreeStrategy:
    """R7: one agent with all formal and retrieval affordances."""

    strategy_id = "chess.single_agent_tree"
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
            max_model_calls=1,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        mode = tree_memory_mode(context, self._memory_mode)
        gateway = context.legality_gateway
        workspace = context.search_workspace
        if gateway is None:
            return self._error("legality_gateway_missing", mode)
        if workspace is None:
            return self._error("search_workspace_missing", mode)

        legal_set = gateway.enumerate_actions()
        legal_moves = tuple(str(action) for action in legal_set.actions)
        legal_context: dict[str, JsonValue] = {
            "count": len(legal_moves),
            "hash": str(legal_set.legal_hash),
            "moves": list(legal_moves),
        }
        retrieved = tree_retrieve_memory(
            memory=context.search_memory,
            workspace=workspace,
            mode=mode,
        )
        reply_scope = _search_value(context, "reply_scope", "all")
        root_branches: dict[str, str] = {}
        root_summaries: list[dict[str, JsonValue]] = []
        if reply_scope == "all":
            root_branches, root_summaries = self._prepare_all_root_affordances(
                legal_moves=legal_moves,
                gateway=gateway,
                workspace=workspace,
                max_roots=tree_search_int(context, "max_affordance_roots", 64),
            )

        position = build_observation_text(tree_as_observation(observation))
        affordances = tree_affordance_text(legal_context, mode, retrieved)
        if root_summaries:
            affordances += (
                "\nROOT BRANCH AFFORDANCES (legal replies from each hypothetical child)\n"
                + _root_affordance_text(root_summaries)
            )
        if _search_value(context, "prompt_mode", "standard") == "forced_replies":
            affordances += (
                "\nFORCED-REPLY CHECKLIST\n"
                "For every candidate, check opponent checks, captures, mate threats, "
                "recaptures and king escapes before selecting the root move."
            )

        prompt = (
            "You are one single chess research agent. Do all work in one response: "
            "map the position, inspect tactical and king-safety risks, choose candidates, "
            "propose concrete variants and select exactly one root move. The formal "
            "gateway data below is authoritative for legal actions. You may propose a "
            "small number of illegal probes so the RulesKernel can reject them, but "
            "the infinite complement of illegal strings cannot be enumerated. Do not "
            "use Stockfish, tablebases or external evaluation. Return JSON only.\n\n"
            f"POSITION\n{position}\n\n{affordances}\n\n"
            "Schema fields: critical_map, hanging_pieces, tactical_ideas, "
            "candidate_moves, illegal_probes, variants, move, analysis, confidence."
        )
        prompt = apply_prompt_override_text(append_retry_feedback(prompt, context), context)
        report, raw, call = await self._ask(prompt, context)
        calls = [call]
        verdicts = [tree_call_verdict(_ROLE, call)]

        candidate_moves = tree_move_values(report.get("candidate_moves"))
        illegal_probes = tree_move_values(report.get("illegal_probes"))
        if reply_scope != "all":
            root_branches, root_summaries = self._prepare_candidate_affordances(
                candidate_moves=candidate_moves,
                illegal_probes=illegal_probes,
                gateway=gateway,
                workspace=workspace,
                max_roots=tree_search_int(context, "max_root_branches", 4),
                verdicts=verdicts,
            )
        else:
            self._record_illegal_probes(
                illegal_probes=illegal_probes,
                workspace=workspace,
                verdicts=verdicts,
            )
        variants = self._materialize_variants(
            report=report,
            root_branches=root_branches,
            workspace=workspace,
            memory=context.search_memory,
            context=context,
            verdicts=verdicts,
        )
        final_action = tree_parse_move(report.get("move")) or tree_first_uci(raw)
        final_validation: dict[str, JsonValue] | None = None
        if final_action is not None:
            checked = gateway.validate(final_action)
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
            "workflow": [_ROLE],
            "single_agent": True,
            "position_report": cast(JsonValue, report),
            "memory_mode": mode,
            "reply_scope": reply_scope,
            "legal_action_set": legal_context,
            "retrieved_memory": cast(JsonValue, retrieved),
            "illegal_probes": cast(JsonValue, illegal_probes),
            "root_branches": cast(JsonValue, root_summaries),
            "variant_branches": cast(JsonValue, variants),
            "final_validation": cast(JsonValue, final_validation),
            "model_only": True,
            "engine_used": False,
        }
        candidates = tuple(
            Candidate(action=move, origin="single_agent")
            for move in tree_unique(candidate_moves)
            if move in root_branches
        )
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R7",
            calls=tuple(calls),
            candidates=candidates,
            verdicts=(
                *verdicts,
                Verdict(kind="final_action_parsed" if final_action else "parse_error"),
            ),
            selection_rationale=rationale,
            final_action=final_action,
            termination_reason="selected" if final_action else "parse_error",
            assistance_impacts=(
                AssistanceImpact(
                    h=HClass.H4,
                    k=KClass.K6 if mode == "persistent" else KClass.K0,
                    source="single_agent_tree",
                ),
            ),
        )

    def _prepare_all_root_affordances(
        self,
        *,
        legal_moves: tuple[str, ...],
        gateway: Any,
        workspace: Any,
        max_roots: int,
    ) -> tuple[dict[str, str], list[dict[str, JsonValue]]]:
        branches: dict[str, str] = {}
        summaries: list[dict[str, JsonValue]] = []
        for move in legal_moves[:max_roots]:
            result = workspace.try_move(
                workspace.root_id,
                move,
                created_by="single-agent:formal-affordance",
            )
            if not result.get("legal") or not result.get("child_node_id"):
                continue
            child_id = str(result["child_node_id"])
            child_state = workspace.state(child_id)
            reply_set = gateway.bind_state(child_state).enumerate_actions()
            branches[move] = child_id
            summaries.append(
                {
                    "root_move": move,
                    "node_id": child_id,
                    "fen": str(getattr(child_state, "fen", "")),
                    "legal_reply_count": len(reply_set.actions),
                    "legal_reply_hash": str(reply_set.legal_hash),
                    "legal_reply_moves": [str(action) for action in reply_set.actions],
                }
            )
        return branches, summaries

    def _prepare_candidate_affordances(
        self,
        *,
        candidate_moves: list[str],
        illegal_probes: list[str],
        gateway: Any,
        workspace: Any,
        max_roots: int,
        verdicts: list[Verdict],
    ) -> tuple[dict[str, str], list[dict[str, JsonValue]]]:
        branches: dict[str, str] = {}
        summaries: list[dict[str, JsonValue]] = []
        for move in tree_unique(candidate_moves + illegal_probes):
            if len(branches) >= max_roots and move not in illegal_probes:
                continue
            result = workspace.try_move(
                workspace.root_id,
                move,
                created_by="single-agent:candidate",
            )
            if not result.get("legal") or not result.get("child_node_id"):
                verdicts.append(
                    Verdict(
                        kind="illegal_probe_rejected",
                        message=f"{move}: {result.get('reason', 'illegal')}",
                    )
                )
                continue
            child_id = str(result["child_node_id"])
            child_state = workspace.state(child_id)
            reply_set = gateway.bind_state(child_state).enumerate_actions()
            branches[move] = child_id
            summaries.append(
                {
                    "root_move": move,
                    "node_id": child_id,
                    "fen": str(getattr(child_state, "fen", "")),
                    "legal_reply_count": len(reply_set.actions),
                    "legal_reply_hash": str(reply_set.legal_hash),
                    "legal_reply_moves": [str(action) for action in reply_set.actions],
                }
            )
        return branches, summaries

    def _record_illegal_probes(
        self,
        *,
        illegal_probes: list[str],
        workspace: Any,
        verdicts: list[Verdict],
    ) -> None:
        for move in tree_unique(illegal_probes):
            result = workspace.try_move(
                workspace.root_id,
                move,
                created_by="single-agent:illegal-probe",
            )
            if not result.get("legal"):
                verdicts.append(
                    Verdict(
                        kind="illegal_probe_rejected",
                        message=f"{move}: {result.get('reason', 'illegal')}",
                    )
                )

    def _materialize_variants(
        self,
        *,
        report: dict[str, Any],
        root_branches: dict[str, str],
        workspace: Any,
        memory: Any,
        context: DecisionContext,
        verdicts: list[Verdict],
    ) -> list[dict[str, JsonValue]]:
        records: list[dict[str, JsonValue]] = []
        raw_variants = report.get("variants")
        if not isinstance(raw_variants, list):
            return records
        max_variants = tree_search_int(context, "max_variant_branches", 6)
        for raw in cast(list[Any], raw_variants)[:max_variants]:
            if not isinstance(raw, Mapping):
                continue
            data = cast(Mapping[str, Any], raw)
            root = tree_parse_move(data.get("root_move"))
            reply = tree_parse_move(data.get("reply_move"))
            if root is None or reply is None or root not in root_branches:
                verdicts.append(Verdict(kind="variant_unparsed", message="root or reply missing"))
                continue
            result = workspace.try_move(
                root_branches[root],
                reply,
                created_by="single-agent:variant",
            )
            record: dict[str, JsonValue] = {
                "root_move": root,
                "reply_move": reply,
                "legal": bool(result.get("legal")),
                "child_node_id": (
                    str(result["child_node_id"]) if result.get("child_node_id") else None
                ),
                "assessment": str(data.get("assessment", ""))[:1000],
                "risks": [
                    str(item)[:500]
                    for item in cast(list[Any], data.get("risks", []))
                    if isinstance(item, str)
                ],
            }
            if result.get("legal") and result.get("child_node_id"):
                tree_record_memory(
                    memory,
                    node_id=str(result["child_node_id"]),
                    kind="refutation",
                    content=f"single agent variant {root} reply {reply}",
                    generated_by=str(context.model),
                    verdicts=verdicts,
                )
            else:
                record["reason"] = str(result.get("reason", "illegal"))
                verdicts.append(
                    Verdict(kind="variant_reply_rejected", message=f"{root} -> {reply}")
                )
            for probe in tree_move_values(data.get("illegal_reply_probes")):
                probe_result = workspace.try_move(
                    root_branches[root],
                    probe,
                    created_by="single-agent:illegal-reply-probe",
                )
                if not probe_result.get("legal"):
                    verdicts.append(
                        Verdict(
                            kind="illegal_reply_probe_rejected",
                            message=f"{root} -> {probe}: {probe_result.get('reason', 'illegal')}",
                        )
                    )
            records.append(record)
        return records

    async def _ask(
        self,
        prompt: str,
        context: DecisionContext,
    ) -> tuple[dict[str, Any], str, CallRecord]:
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text=prompt),)),),
            output_constraint=OutputConstraint.model_validate(
                {"format": "json_schema", "schema": _REPORT_SCHEMA}
            ),
            required_capabilities=frozenset({Capability.JSON_SCHEMA_OUTPUT}),
            extensions={
                "chess.strategy": _STRATEGY_NAME,
                "chess.agent_role": _ROLE,
            },
            metadata={"agent_role": _ROLE, "workflow": "single-agent-tree"},
        )
        before = tree_recorded_attempt_ids(context.backend)
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-single-agent-tree:{_ROLE}:{context.seed}",
            metadata={"agent_role": _ROLE},
        )
        try:
            result = await context.backend.infer(request, call_context)
        except Exception as exc:
            code = str(getattr(exc, "stable_code", type(exc).__name__))
            return (
                {"error": code},
                "",
                CallRecord(
                    attempt_id=tree_latest_attempt_id(context.backend, before, _ROLE),
                    request_fingerprint=call_context.fingerprint,
                    response_ok=False,
                    usage=TokenUsage(),
                    failure_code=code,
                ),
            )
        raw = result.response.text().strip()
        return (
            tree_parse_report(raw),
            raw,
            CallRecord(
                attempt_id=tree_latest_attempt_id(context.backend, before, _ROLE),
                request_fingerprint=call_context.fingerprint,
                response_ok=True,
                usage=result.response.usage,
                cost=result.response.cost,
            ),
        )

    def _error(self, reason: str, mode: str) -> DecisionTrace:
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R7",
            verdicts=(Verdict(kind="configuration_error", message=reason),),
            selection_rationale={
                "workflow": [_ROLE],
                "single_agent": True,
                "memory_mode": mode,
                "legal_actions_exposed": False,
            },
            final_action=None,
            termination_reason=reason,
            assistance_impacts=(
                AssistanceImpact(
                    h=HClass.H4,
                    k=KClass.K6 if mode == "persistent" else KClass.K0,
                    source="single_agent_tree",
                ),
            ),
        )


def _search_value(context: DecisionContext, name: str, default: str) -> str:
    search = context.config.get("search")
    if isinstance(search, dict):
        value = search.get(name)
        if isinstance(value, str):
            return value
    return default


def _root_affordance_text(summaries: list[dict[str, JsonValue]]) -> str:
    blocks: list[str] = []
    for summary in summaries:
        root = str(summary.get("root_move", ""))
        moves = summary.get("legal_reply_moves", [])
        rendered_moves = ", ".join(str(move) for move in cast(list[Any], moves))
        blocks.append(
            f"LEGAL REPLIES AFTER {root} "
            f"(count={summary.get('legal_reply_count', 0)}, "
            f"hash={summary.get('legal_reply_hash', '')}): {rendered_moves}"
        )
    return "\n".join(blocks)
