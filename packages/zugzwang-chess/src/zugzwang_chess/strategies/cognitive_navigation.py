"""Chess cognitive navigation strategy (PRD §38.8; CB-WO-07).

``chess.cognitive_navigation`` is a NEW strategy: no baseline in
``strategies/`` is modified. It implements the DecisionStrategy port over a
decision session: observe the focus node, expand a legal action seen in the
previous result (causal feedback — the next operation depends on the previous
result), and finalize a root-legal UCI move. Finalization is validated
against the root packet before the loop commits it; an action that is legal
elsewhere but not at the focus is never selected (TEST-024).
"""

from __future__ import annotations

from typing import Any, cast

from zugzwang_core.domain.assistance import AssistanceImpact
from zugzwang_core.ports.strategy import (
    CallRecord,
    Candidate,
    DecisionContext,
    DecisionTrace,
    StrategyDescriptor,
    Verdict,
)

STRATEGY_ID = "chess.cognitive_navigation"
STRATEGY_VERSION = "0.1.0"


class CognitiveNavigationStrategy:
    """Adaptive L0 navigation: observe → expand → finalize (bounded)."""

    strategy_id = STRATEGY_ID
    strategy_version = STRATEGY_VERSION
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, *, max_rounds: int = 4) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        self._max_rounds = max_rounds

    @property
    def descriptor(self) -> StrategyDescriptor:
        return StrategyDescriptor(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            plugin_api=self.plugin_api,
            declared_regime="R5",
            declared_assistance_h="H0",
            declared_assistance_k="K0",
            consumes_legal_actions=True,
            produces_candidates=True,
            max_model_calls=self._max_rounds,
        )

    async def decide(self, observation: Any, context: DecisionContext) -> DecisionTrace:
        """Propose the next operation from the transcript so far.

        ``observation`` carries ``node_id`` (focus) and ``transcript`` (prior
        broker results). Round 0 observes; later rounds expand the first legal
        action of the previous observation (causal feedback); the final round
        finalizes the first root-legal UCI.
        """
        node_id = _focus_node(observation)
        transcript = _transcript(observation)
        round_no = len(transcript)
        verdicts: list[Verdict] = []
        candidates: list[Candidate] = []
        invocations: list[str] = []

        if round_no == 0:
            invocations.append(f"board_observe:{node_id}")
            verdicts.append(Verdict(kind="observe", message=f"observing {node_id}"))
        elif round_no < self._max_rounds - 1:
            action_id = _first_action(transcript)
            if action_id is None:
                verdicts.append(
                    Verdict(kind="no_action", message="no legal action to expand; abort")
                )
                return DecisionTrace(
                    strategy_id=self.strategy_id,
                    strategy_version=self.strategy_version,
                    declared_regime="R5",
                    verdicts=tuple(verdicts),
                    termination_reason="aborted",
                )
            invocations.append(f"board_expand:{node_id}:{action_id}")
            candidates.append(Candidate(action=action_id, origin="expansion"))
            verdicts.append(Verdict(kind="expand", message=f"expanding {action_id}"))
        else:
            uci = _first_uci(transcript)
            if uci is None:
                verdicts.append(Verdict(kind="no_action", message="no UCI to finalize; abort"))
                return DecisionTrace(
                    strategy_id=self.strategy_id,
                    strategy_version=self.strategy_version,
                    declared_regime="R5",
                    verdicts=tuple(verdicts),
                    termination_reason="aborted",
                )
            invocations.append(f"finalize:{node_id}:{uci}")
            candidates.append(Candidate(action=uci, origin="model"))
            verdicts.append(Verdict(kind="finalize", message=f"finalizing {uci}"))

        return DecisionTrace(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            declared_regime="R5",
            calls=(
                CallRecord(
                    attempt_id=f"nav-{round_no}",
                    response_ok=True,
                    usage=_empty_usage(),
                ),
            ),
            candidates=tuple(candidates),
            tool_invocations=tuple(invocations),
            verdicts=tuple(verdicts),
            selection_rationale={"round": round_no, "focus": node_id},
            final_action=candidates[0].action if candidates else None,
            termination_reason="selected" if candidates else "exploring",
        )


def propose_from_transcript(
    transcript: list[dict[str, Any]], node_id: str, max_rounds: int = 4
) -> dict[str, Any]:
    """Pure proposal function: next operation given prior results (TEST-023).

    Returns {"op": "observe"} on round 0, {"op": "expand", "action_id": ...}
    when the transcript's last observation carries legal actions, or
    {"op": "finalize", "uci": ...} on the last round. The expand/finalize
    choices are read from the previous result — never invented.
    """
    round_no = len(transcript)
    if round_no == 0:
        return {"op": "observe", "node_id": node_id}
    if round_no < max_rounds - 1:
        action_id = _first_action(transcript)
        if action_id is None:
            return {"op": "abort", "node_id": node_id}
        return {"op": "expand", "node_id": node_id, "action_id": action_id}
    uci = _first_uci(transcript)
    if uci is None:
        return {"op": "abort", "node_id": node_id}
    return {"op": "finalize", "node_id": node_id, "uci": uci}


def _as_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[str, Any], value)


def _focus_node(observation: Any) -> str:
    record = _as_record(observation)
    if record is not None:
        node = record.get("node_id")
        if isinstance(node, str) and node:
            return node
    return "node-root"


def _transcript(observation: Any) -> list[dict[str, Any]]:
    record = _as_record(observation)
    if record is not None:
        items: Any = record.get("transcript")
        if isinstance(items, list):
            return [item for item in cast(list[Any], items) if isinstance(item, dict)]
    return []


def _last_result(transcript: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in transcript[::-1]:
        result = _as_record(entry.get("result"))
        if result is not None:
            return result
    return None


def _first_legal_item(transcript: list[dict[str, Any]]) -> dict[str, Any] | None:
    result = _last_result(transcript)
    if result is None:
        return None
    packet = _as_record(result.get("packet"))
    if packet is None:
        return None
    legal = _as_record(packet.get("legal_actions"))
    if legal is None:
        return None
    raw_items: Any = legal.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return None
    return _as_record(cast(list[Any], raw_items)[0])


def _first_action(transcript: list[dict[str, Any]]) -> str | None:
    first = _first_legal_item(transcript)
    if first is None:
        return None
    action_id = first.get("action_id")
    return action_id if isinstance(action_id, str) else None


def _first_uci(transcript: list[dict[str, Any]]) -> str | None:
    first = _first_legal_item(transcript)
    if first is None:
        return None
    uci = first.get("uci")
    return uci if isinstance(uci, str) else None


def _empty_usage() -> Any:
    from zugzwang_core.domain.money import TokenUsage, UsageSource

    return TokenUsage(input_tokens=0, output_tokens=0, source=UsageSource.UNKNOWN)


def assistance() -> AssistanceImpact | None:
    return None
