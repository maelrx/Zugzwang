"""R6-BatchedTree: model-only candidate search over formal transitions."""

from __future__ import annotations

import json
import re
from typing import Any, cast

from zugzwang_core.domain.assistance import AssistanceImpact, HClass, KClass
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

_UCI_TOKEN = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b")


class BatchedTreeStrategy:
    """Build and judge a small hypothetical tree using the same model only."""

    strategy_id = "chess.r6_batched_tree"
    strategy_version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(
        self,
        *,
        initial_candidates: int = 4,
        judges: int = 3,
        include_refuter: bool = True,
    ) -> None:
        self._initial_candidates = max(1, initial_candidates)
        self._judges = max(1, judges)
        self._include_refuter = include_refuter

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R6",
            declared_assistance_h="H4",
            declared_assistance_k="K0",
            consumes_legal_actions=False,
            produces_candidates=True,
            max_model_calls=1
            + self._judges
            + (self._initial_candidates if self._include_refuter else 0),
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        workspace = context.search_workspace
        if workspace is None:
            return self._error("search_workspace_missing")
        calls: list[CallRecord] = []
        verdicts: list[Verdict] = []
        candidates: list[Candidate] = []
        observation_data = (
            cast(dict[str, JsonValue], observation) if isinstance(observation, dict) else {}
        )
        raw, record = await self._call_candidate_generator(observation_data, context)
        calls.append(record)
        moves = _candidate_moves(raw)[: self._initial_candidates]
        if not moves:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R6",
                calls=tuple(calls),
                verdicts=(Verdict(kind="parse_error", message="no candidate move found"),),
                final_action=None,
                termination_reason="parse_error",
                assistance_impacts=(
                    AssistanceImpact(h=HClass.H4, k=KClass.K0, source="model_only_search"),
                ),
            )

        legal_branches: list[tuple[str, str]] = []
        retrieved_memory: list[str] = []
        for move in moves:
            try:
                branch = workspace.try_move(
                    workspace.root_id,
                    move,
                    created_by="candidate-generator:model",
                )
            except Exception as exc:
                verdicts.append(Verdict(kind="search_error", message=str(exc)[:200]))
                continue
            candidate = Candidate(action=move, origin="model_candidate")
            candidates.append(candidate)
            if branch.get("legal") and branch.get("child_node_id"):
                child_id = str(branch["child_node_id"])
                legal_branches.append((move, child_id))
                verdicts.append(Verdict(kind="legal_branch", message=move))
                memory = context.search_memory
                if memory is not None:
                    memory.record(
                        node_id=child_id,
                        kind="candidate",
                        content=f"model proposed {move}",
                        generated_by=str(context.model),
                    )
                    retrieved = memory.retrieve(
                        "exact_state",
                        child_id,
                        _RetrievalBudget(max_items=4),
                    )
                    retrieved_memory.extend(item.memory_id for item in retrieved.items)
            else:
                verdicts.append(
                    Verdict(
                        kind="illegal_branch_pruned",
                        message=f"model candidate {move} rejected by RulesKernel",
                    )
                )

        if not legal_branches:
            return DecisionTrace(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                declared_regime="R6",
                calls=tuple(calls),
                candidates=tuple(candidates),
                verdicts=tuple(verdicts),
                final_action=None,
                termination_reason="no_legal_candidate",
                assistance_impacts=(
                    AssistanceImpact(h=HClass.H4, k=KClass.K0, source="model_only_search"),
                ),
            )

        votes: dict[str, int] = {move: 0 for move, _ in legal_branches}
        if self._include_refuter:
            refuted_branches: list[tuple[str, str]] = []
            for move, child_id in legal_branches:
                try:
                    reply_raw, refuter_record = await self._call_refuter(
                        move, child_id, workspace, context
                    )
                    calls.append(refuter_record)
                except Exception as exc:
                    verdicts.append(
                        Verdict(kind="refuter_error", message=f"{move}: {str(exc)[:160]}")
                    )
                    refuted_branches.append((move, child_id))
                    continue
                replies = _candidate_moves(reply_raw)
                if not replies:
                    verdicts.append(Verdict(kind="refuter_unparsed", message=move))
                    refuted_branches.append((move, child_id))
                    continue
                reply = replies[0]
                try:
                    response_branch = workspace.try_move(
                        child_id,
                        reply,
                        created_by="adversarial-refuter:model",
                    )
                except Exception as exc:
                    verdicts.append(
                        Verdict(kind="refuter_search_error", message=f"{move}: {str(exc)[:160]}")
                    )
                    refuted_branches.append((move, child_id))
                    continue
                if response_branch.get("legal") and response_branch.get("child_node_id"):
                    refuted_id = str(response_branch["child_node_id"])
                    refuted_branches.append((move, refuted_id))
                    verdicts.append(Verdict(kind="adversarial_reply", message=f"{move} -> {reply}"))
                    memory = context.search_memory
                    if memory is not None:
                        memory.record(
                            node_id=refuted_id,
                            kind="refutation",
                            content=f"model refutation {reply} against {move}",
                            generated_by=str(context.model),
                        )
                else:
                    verdicts.append(
                        Verdict(kind="refuter_illegal_reply", message=f"{move} -> {reply}")
                    )
                    refuted_branches.append((move, child_id))
            legal_branches = refuted_branches

        if len(legal_branches) == 1:
            winner = legal_branches[0][0]
        else:
            winner = legal_branches[0][0]
            for judge_index in range(self._judges):
                answer, judge_record = await self._call_blind_judge(
                    legal_branches, workspace, context, judge_index
                )
                calls.append(judge_record)
                selected = _select_label(answer, legal_branches)
                if selected is not None:
                    votes[selected] += 1
                    winner = max(votes, key=lambda move: (votes[move], -_move_index(move, votes)))
                    verdicts.append(
                        Verdict(kind="blind_judge", message=f"judge {judge_index + 1}: {selected}")
                    )
                else:
                    verdicts.append(
                        Verdict(kind="blind_judge_unparsed", message=f"judge {judge_index + 1}")
                    )

        scored = tuple(
            candidate.model_copy(update={"score": float(votes.get(str(candidate.action), 0))})
            for candidate in candidates
        )
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R6",
            calls=tuple(calls),
            candidates=scored,
            verdicts=tuple(verdicts),
            selection_rationale=cast(
                dict[str, JsonValue],
                {
                    "method": "blind_pairwise_majority",
                    "judges": self._judges if len(legal_branches) > 1 else 0,
                    "refuter_enabled": self._include_refuter,
                    "votes": votes,
                    "engine_available_before_decision": False,
                    "memory_items_retrieved": retrieved_memory,
                },
            ),
            final_action=winner,
            termination_reason="selected",
            assistance_impacts=(
                AssistanceImpact(h=HClass.H4, k=KClass.K0, source="model_only_search"),
            ),
        )

    async def _call_refuter(
        self,
        root_move: str,
        node_id: str,
        workspace: Any,
        context: DecisionContext,
    ) -> tuple[str, CallRecord]:
        child = workspace.state(node_id)
        fen = getattr(child, "fen", "")
        prompt = (
            "Act as an adversarial model-only refuter. Find one strongest reply "
            "against the candidate below. The rules kernel will validate it. "
            "Return one UCI move only. Do not use an engine.\n\n"
            f"Candidate: {root_move}\nPosition after candidate: {fen}"
        )
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text=prompt),)),),
            output_constraint=OutputConstraint(format="text"),
            extensions={"chess.strategy": "r6_batched_tree", "chess.phase": "refuter"},
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-r6-refuter:{context.seed}:{root_move}",
        )
        result = await context.backend.infer(request, call_context)
        return result.response.text().strip(), CallRecord(
            attempt_id=call_context.attempt_id or "att-placeholder",
            response_ok=True,
            usage=result.response.usage,
        )

    async def _call_candidate_generator(
        self, observation: dict[str, JsonValue], context: DecisionContext
    ) -> tuple[str, CallRecord]:
        prompt = (
            "Build a small candidate set for this chess position. The rules kernel will "
            "validate every edge. Do not assume a legal move list. Return JSON only in "
            'the form {"candidates":[{"move":"e2e4","analysis":"..."}]} .\n\n'
            + build_observation_text(observation)
        )
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text=prompt),)),),
            output_constraint=OutputConstraint(format="json_object"),
            extensions={"chess.strategy": "r6_batched_tree", "chess.phase": "candidates"},
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-r6-candidates:{context.seed}",
        )
        result = await context.backend.infer(request, call_context)
        return result.response.text().strip(), CallRecord(
            attempt_id=call_context.attempt_id or "att-placeholder",
            response_ok=True,
            usage=result.response.usage,
        )

    async def _call_blind_judge(
        self,
        branches: list[tuple[str, str]],
        workspace: Any,
        context: DecisionContext,
        judge_index: int,
    ) -> tuple[str, CallRecord]:
        options: list[str] = []
        for index, (move, child_id) in enumerate(branches):
            child = workspace.state(child_id)
            fen = getattr(child, "fen", "")
            options.append(f"Option {index + 1} ({move}): {fen}")
        prompt = (
            "You are a blind model-only position judge. Compare the hypothetical "
            "positions below and choose the option you prefer for the side to move. "
            "No engine or external chess evaluation is available. Reply with only "
            "the option number.\n\n" + "\n".join(options)
        )
        request = ModelRequest(
            model=context.model,
            messages=(Message(role=MessageRole.USER, parts=(TextPart(text=prompt),)),),
            output_constraint=OutputConstraint(format="text"),
            extensions={
                "chess.strategy": "r6_batched_tree",
                "chess.phase": "blind_judge",
                "judge_index": judge_index,
            },
        )
        call_context = CallContext(
            run_id=context.run_id,
            episode_id=context.episode_id,
            step_id=context.step_id,
            fingerprint=f"chess-r6-judge:{context.seed}:{judge_index}",
        )
        result = await context.backend.infer(request, call_context)
        return result.response.text().strip(), CallRecord(
            attempt_id=call_context.attempt_id or "att-placeholder",
            response_ok=True,
            usage=result.response.usage,
        )

    def _error(self, reason: str) -> DecisionTrace:
        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R6",
            verdicts=(Verdict(kind="configuration_error", message=reason),),
            final_action=None,
            termination_reason=reason,
            assistance_impacts=(
                AssistanceImpact(h=HClass.H4, k=KClass.K0, source="model_only_search"),
            ),
        )


def _candidate_moves(raw: str) -> list[str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return list(dict.fromkeys(_UCI_TOKEN.findall(raw)))
    if not isinstance(payload, dict):
        return []
    payload_data = cast(dict[str, Any], payload)
    items_raw = payload_data.get("candidates")
    if not isinstance(items_raw, list):
        return []
    items = cast(list[Any], items_raw)
    moves: list[str] = []
    for item in items:
        if isinstance(item, dict):
            item_data = cast(dict[str, Any], item)
            move = item_data.get("move") or item_data.get("action")
            if isinstance(move, str) and _UCI_TOKEN.fullmatch(move.strip()):
                moves.append(move.strip())
    return list(dict.fromkeys(moves))


def _select_label(raw: str, branches: list[tuple[str, str]]) -> str | None:
    match = re.search(r"\b([1-9][0-9]*)\b", raw)
    if match is None:
        return None
    index = int(match.group(1)) - 1
    return branches[index][0] if 0 <= index < len(branches) else None


def _move_index(move: str, votes: dict[str, int]) -> int:
    return list(votes).index(move)


class _RetrievalBudget:
    def __init__(self, *, max_items: int) -> None:
        self.max_items = max_items
