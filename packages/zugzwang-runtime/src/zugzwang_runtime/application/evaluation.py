"""Post-hoc evaluation and reporting services (design §16, §21).

Evaluation never alters the original run: metrics append with provenance;
reports group by declared assistance and never mix system classes.
"""

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from zugzwang_core.domain.artifacts import ArtifactRef
from zugzwang_core.domain.events import JsonValue
from zugzwang_core.domain.ids import new_id

from ..artifacts.cas import ContentAddressedStore
from ..persistence.repositories import (
    EpisodeRepository,
    EventRepository,
    MetricObservationRepository,
    RunRepository,
    StepRepository,
)


class EvaluationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    evaluator_id: str
    observations: int
    metrics: dict[str, Any]


def build_evaluation_steps(
    *,
    run_id: str,
    runs: RunRepository,
    episodes: EpisodeRepository,
    steps: StepRepository,
    cas: ContentAddressedStore,
) -> list[dict[str, Any]]:
    """Reconstruct (fen, action, side) tuples for every committed model step.

    Positions come from CAS snapshots; actions from committed projections.
    This is replay — no provider call, no engine in the loop.
    """
    evaluation_steps: list[dict[str, Any]] = []
    for episode_row in episodes.for_run(run_id):
        episode_id = episode_row["episode_id"]
        step_rows = steps.for_episode(episode_id)
        committed = [r for r in step_rows if r["status"] == "COMMITTED"]
        initial_ref = episode_row.get("initial_state_artifact_id")
        for index, row in enumerate(committed):
            action_json: dict[str, Any] = dict(row.get("action_json") or {})
            action = action_json.get("action")
            if not isinstance(action, str) or action_json.get("kind"):
                continue
            state_ref_id = (
                committed[index - 1]["transition_artifact_id"] if index > 0 else initial_ref
            )
            if not state_ref_id:
                continue
            try:
                snapshot = cas.get(ArtifactRef.parse(str(state_ref_id)))
            except Exception:
                continue
            state_data = json.loads(snapshot.data.decode("utf-8"))
            fen = state_data.get("fen")
            if not isinstance(fen, str):
                continue
            side = "white" if fen.split(" ")[1] == "w" else "black"
            evaluation_steps.append(
                {
                    "run_id": run_id,
                    "episode_id": episode_id,
                    "step_id": row["step_id"],
                    "fen": fen,
                    "moves": list(state_data.get("moves", [])),
                    "action": action,
                    "side_to_move": side,
                    "fullmove_number": (int(fen.split(" ")[5]) if len(fen.split(" ")) > 5 else 1),
                }
            )
    return evaluation_steps


class EvaluateRunService:
    """Runs a post-hoc evaluator over one run and appends metric observations."""

    def __init__(
        self,
        *,
        runs: RunRepository,
        episodes: EpisodeRepository,
        steps: StepRepository,
        metrics: MetricObservationRepository,
        cas: ContentAddressedStore,
    ) -> None:
        self._runs = runs
        self._episodes = episodes
        self._steps = steps
        self._metrics = metrics
        self._cas = cas

    async def evaluate(
        self,
        run_id: str,
        evaluator: Any,
        *,
        evaluator_id: str,
    ) -> EvaluationSummary:
        from zugzwang_core.ports.evaluator import EvaluationContext

        row = self._runs.get_run(run_id)
        if row is None:
            raise ValueError(f"run {run_id} not found")
        evaluation_steps = build_evaluation_steps(
            run_id=run_id,
            runs=self._runs,
            episodes=self._episodes,
            steps=self._steps,
            cas=self._cas,
        )
        if not evaluation_steps:
            return EvaluationSummary(
                run_id=run_id, evaluator_id=evaluator_id, observations=0, metrics={}
            )
        context = EvaluationContext(
            run_id=run_id,
            evaluator_config={
                "steps": cast(
                    "list[JsonValue]",
                    [cast("dict[str, JsonValue]", dict(step)) for step in evaluation_steps],
                )
            },
        )
        result = await evaluator.evaluate(context)
        stored = 0
        for observation in result.observations:
            self._metrics.insert(
                {
                    "metric_observation_id": str(new_id("evl")),
                    "run_id": observation.run_id or run_id,
                    "episode_id": observation.episode_id,
                    "step_id": observation.step_id,
                    "metric_definition_id": observation.metric_id,
                    "metric_version": observation.metric_version,
                    "value_num": observation.value_num,
                    "value_text": observation.value_text,
                    "value_json": observation.value_json,
                    "unit": observation.unit,
                    "dimensions_json": observation.dimensions,
                    "provenance_artifact_id": (
                        observation.provenance_artifact.as_id()
                        if observation.provenance_artifact is not None
                        else None
                    ),
                    "evaluator_id": observation.evaluator_id,
                    "evaluator_version": observation.evaluator_version,
                }
            )
            stored += 1
        metrics = _aggregate_observations(result.observations)
        return EvaluationSummary(
            run_id=run_id,
            evaluator_id=evaluator_id,
            observations=stored,
            metrics=metrics,
        )


def _aggregate_observations(observations: Any) -> dict[str, Any]:
    numeric: dict[str, list[float]] = {}
    categorical: dict[str, dict[str, int]] = {}
    for observation in observations:
        if observation.value_num is not None:
            numeric.setdefault(observation.metric_id, []).append(observation.value_num)
        elif observation.value_text is not None:
            counts = categorical.setdefault(observation.metric_id, {})
            counts[observation.value_text] = counts.get(observation.value_text, 0) + 1
    summary: dict[str, Any] = {}
    for metric_id, values in numeric.items():
        ordered = sorted(values)
        summary[metric_id] = {
            "n": len(values),
            "mean": round(sum(values) / len(values), 3),
            "median": round(ordered[len(ordered) // 2], 3),
            "min": round(min(values), 3),
            "max": round(max(values), 3),
        }
    for metric_id, counts in categorical.items():
        summary[metric_id] = dict(counts)
    return summary


class ReportRunService:
    """Markdown + JSON report with honest grouping (design §16.7)."""

    def __init__(
        self,
        *,
        runs: RunRepository,
        episodes: EpisodeRepository,
        steps: StepRepository,
        metrics: MetricObservationRepository,
        events: EventRepository,
    ) -> None:
        self._runs = runs
        self._episodes = episodes
        self._steps = steps
        self._metrics = metrics
        self._events = events

    def report(self, run_id: str) -> dict[str, Any]:
        row = self._runs.get_run(run_id)
        if row is None:
            raise ValueError(f"run {run_id} not found")
        episode_rows = self._episodes.for_run(run_id)
        episodes_data: list[dict[str, Any]] = []
        for episode in episode_rows:
            steps_rows = self._steps.for_episode(episode["episode_id"])
            episodes_data.append(
                {
                    "episode_id": episode["episode_id"],
                    "status": episode["status"],
                    "outcome": episode.get("outcome"),
                    "steps_committed": sum(1 for s in steps_rows if s["status"] == "COMMITTED"),
                    "steps_failed": sum(1 for s in steps_rows if s["status"] == "TERMINAL_FAILURE"),
                }
            )
        metrics_rows = self._metrics.for_run(run_id)
        events_rows = self._events.for_run(run_id)
        provider_calls = sum(1 for e in events_rows if e["event_type"] == "provider.call.completed")
        provider_failures = sum(
            1
            for e in events_rows
            if e["event_type"] in {"provider.call.failed", "provider.call.timeout_unknown"}
        )
        usage_tokens: dict[str, int] = {"input": 0, "output": 0}
        for e in events_rows:
            if e["event_type"] == "provider.call.completed":
                payload: dict[str, Any] = dict(e.get("payload_json") or {})
                usage: dict[str, Any] = dict(payload.get("usage") or {})
                usage_tokens["input"] += int(usage.get("input_tokens", 0) or 0)
                usage_tokens["output"] += int(usage.get("output_tokens", 0) or 0)
        episodes_typed: list[Any] = episodes_data
        report: dict[str, Any] = {
            "run_id": run_id,
            "status": row["status"],
            "condition_id": row["condition_id"],
            "protocol_hash": row["protocol_hash"],
            "declared_assistance": row["declared_assistance"],
            "effective_assistance": row.get("effective_assistance") or "H2",
            "episodes": episodes_typed,
            "operational": {
                "provider_calls": provider_calls,
                "provider_failures": provider_failures,
                "events": len(events_rows),
                "tokens": usage_tokens,
                "cost_status": "unknown",  # GATE-009 pending: no USD claims
            },
            "metrics": [dict(m) for m in metrics_rows],
            "reproducibility": {
                "auditability": True,
                "offline_replay": True,
                "rerunnable": True,
                "deterministic": False,
                "notes": ["remote provider snapshots may change; replay uses stored artifacts"],
            },
        }
        return report

    def to_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            f"# Run report: {report['run_id']}",
            "",
            f"- Status: **{report['status']}**",
            f"- Condition: `{report['condition_id']}`",
            f"- Protocol hash: `{report['protocol_hash']}`",
            f"- Declared assistance: **{report['declared_assistance']}**",
            f"- Effective assistance: **{report['effective_assistance']}**",
            "",
            "## Operational",
            "",
            f"- Provider calls: {report['operational']['provider_calls']}",
            f"- Provider failures: {report['operational']['provider_failures']}",
            f"- Events: {report['operational']['events']}",
            f"- Tokens: {report['operational']['tokens']['input']} in / "
            f"{report['operational']['tokens']['output']} out",
            f"- Cost status: {report['operational']['cost_status']} (no USD claims)",
            "",
            "## Episodes",
            "",
        ]
        for episode in report["episodes"]:
            lines.append(
                f"- {episode['episode_id']}: {episode['status']} "
                f"(committed {episode['steps_committed']}, failed {episode['steps_failed']})"
            )
        if report["metrics"]:
            lines.append("")
            lines.append("## Metrics")
            lines.append("")
            for metric in report["metrics"]:
                value = (
                    metric.get("value_num")
                    if metric.get("value_num") is not None
                    else metric.get("value_text")
                )
                lines.append(
                    f"- {metric['metric_definition_id']}@{metric['metric_version']}: "
                    f"{value} {metric['unit']}"
                )
        lines.append("")
        lines.append("## What this result measures — and does not")
        lines.append("")
        lines.append(
            "This report describes ONE run of ONE condition. It does not establish "
            "system-level claims: no cross-condition statistics, no Elo, and no cost "
            "claims (cost status is unknown until GATE-009 is ratified). Effective "
            "assistance is computed from observed impacts, never from declaration."
        )
        return "\n".join(lines)
