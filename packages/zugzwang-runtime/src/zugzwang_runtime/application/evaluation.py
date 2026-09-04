"""Post-hoc evaluation and reporting services (design §16, §21).

Evaluation never alters the original run: metrics append with provenance;
reports group by declared assistance and never mix system classes.
"""

from __future__ import annotations

import json
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from zugzwang_core.domain.artifacts import ArtifactPayload, ArtifactRef
from zugzwang_core.domain.canonical import canonical_json_bytes
from zugzwang_core.domain.clocks import to_iso_z, utc_now
from zugzwang_core.domain.events import EventContext, EventEnvelope, JsonValue
from zugzwang_core.domain.ids import new_id

from ..artifacts.cas import ContentAddressedStore
from ..persistence.repositories import (
    ArtifactRepository,
    EpisodeRepository,
    EvaluationRunRepository,
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
    evaluation_run_id: str | None = None
    evaluator_version: str | None = None


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
            if not isinstance(action, str) or action_json.get("kind") or action_json.get("policy"):
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
        evaluation_runs: EvaluationRunRepository | None = None,
        events: EventRepository | None = None,
    ) -> None:
        self._runs = runs
        self._episodes = episodes
        self._steps = steps
        self._metrics = metrics
        self._cas = cas
        self._evaluation_runs = evaluation_runs or EvaluationRunRepository(metrics.engine)
        self._events = events or EventRepository(metrics.engine)

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
        descriptor = getattr(evaluator, "descriptor", None)
        evaluator_version = str(getattr(descriptor, "evaluator_version", "unknown"))
        descriptor_data: dict[str, Any]
        if descriptor is not None and hasattr(descriptor, "model_dump"):
            descriptor_data = descriptor.model_dump(mode="json")
        else:
            descriptor_data = {
                "evaluator_id": evaluator_id,
                "evaluator_version": evaluator_version,
            }
        evaluator_metadata = getattr(evaluator, "evaluation_metadata", None)
        if callable(evaluator_metadata):
            evaluator_metadata = evaluator_metadata()
        if isinstance(evaluator_metadata, dict):
            descriptor_data = {"descriptor": descriptor_data, "engine": evaluator_metadata}
        evaluation_run_id = str(new_id("eval"))
        self._evaluation_runs.insert(
            {
                "evaluation_run_id": evaluation_run_id,
                "source_run_id": run_id,
                "evaluator_id": evaluator_id,
                "evaluator_version": evaluator_version,
                "engine_json": descriptor_data,
                "config_json": {},
                "status": "RUNNING",
                "created_at": to_iso_z(utc_now()),
            }
        )
        self._append_evaluation_event(
            run_id,
            "evaluation.run.started",
            {"evaluation_run_id": evaluation_run_id, "evaluator_id": evaluator_id},
        )
        evaluation_steps = build_evaluation_steps(
            run_id=run_id,
            runs=self._runs,
            episodes=self._episodes,
            steps=self._steps,
            cas=self._cas,
        )
        if not evaluation_steps:
            self._evaluation_runs.update(
                evaluation_run_id,
                {"status": "COMPLETED", "finished_at": to_iso_z(utc_now())},
            )
            self._append_evaluation_event(
                run_id,
                "evaluation.run.completed",
                {"evaluation_run_id": evaluation_run_id, "observations": 0},
            )
            return EvaluationSummary(
                run_id=run_id,
                evaluator_id=evaluator_id,
                observations=0,
                metrics={},
                evaluation_run_id=evaluation_run_id,
                evaluator_version=evaluator_version,
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
        try:
            result = await evaluator.evaluate(context)
        except Exception as exc:
            self._evaluation_runs.update(
                evaluation_run_id,
                {
                    "status": "FAILED",
                    "finished_at": to_iso_z(utc_now()),
                    "failure_code": str(getattr(exc, "stable_code", type(exc).__name__))[:128],
                },
            )
            self._append_evaluation_event(
                run_id,
                "evaluation.run.failed",
                {
                    "evaluation_run_id": evaluation_run_id,
                    "failure_code": str(getattr(exc, "stable_code", type(exc).__name__)),
                },
            )
            raise
        provenance_ref: ArtifactRef | None = None
        analysis_records = getattr(evaluator, "analysis_records", ())
        if isinstance(analysis_records, (list, tuple)) and analysis_records:
            provenance_data = canonical_json_bytes(
                {
                    "schema_version": "zgw.evaluation-trace/v1",
                    "evaluation_run_id": evaluation_run_id,
                    "source_run_id": run_id,
                    "evaluator_id": evaluator_id,
                    "evaluator_version": evaluator_version,
                    "records": analysis_records,
                }
            )
            provenance_ref = self._cas.put(
                ArtifactPayload(
                    media_type="application/vnd.zugzwang.evaluation-trace+json",
                    data=provenance_data,
                ),
                redaction_policy="standard",
            )
            ArtifactRepository(self._metrics.engine).insert_artifact(
                {
                    "artifact_id": provenance_ref.as_id(),
                    "algorithm": "sha256",
                    "size_bytes": len(provenance_data),
                    "media_type": "application/vnd.zugzwang.evaluation-trace+json",
                    "relative_path": provenance_ref.storage_path(),
                    "created_at": to_iso_z(utc_now()),
                    "redaction_policy": "standard",
                }
            )
            self._evaluation_runs.update(
                evaluation_run_id,
                {"config_json": {"analysis_trace_artifact_id": provenance_ref.as_id()}},
            )
        stored = 0
        for observation in result.observations:
            self._metrics.insert(
                {
                    "metric_observation_id": str(new_id("evl")),
                    "run_id": observation.run_id or run_id,
                    "evaluation_run_id": evaluation_run_id,
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
                        else provenance_ref.as_id()
                        if provenance_ref is not None
                        else None
                    ),
                    "evaluator_id": observation.evaluator_id,
                    "evaluator_version": observation.evaluator_version,
                }
            )
            stored += 1
        self._evaluation_runs.update(
            evaluation_run_id,
            {"status": "COMPLETED", "finished_at": to_iso_z(utc_now())},
        )
        self._append_evaluation_event(
            run_id,
            "evaluation.run.completed",
            {"evaluation_run_id": evaluation_run_id, "observations": stored},
        )
        metrics = _aggregate_observations(result.observations)
        return EvaluationSummary(
            run_id=run_id,
            evaluator_id=evaluator_id,
            observations=stored,
            metrics=metrics,
            evaluation_run_id=evaluation_run_id,
            evaluator_version=evaluator_version,
        )

    def _append_evaluation_event(
        self, run_id: str, event_type: str, payload: dict[str, JsonValue]
    ) -> None:
        envelope = EventEnvelope.create(
            event_type=event_type,
            payload=payload,
            stream_type="run",
            stream_id=run_id,
            sequence=0,
            context=EventContext(run_id=run_id),
        )
        self._events.append_event(
            {
                "event_id": envelope.event_id,
                "run_id": run_id,
                "episode_id": None,
                "step_id": None,
                "attempt_id": None,
                "stream_type": "run",
                "stream_id": run_id,
                "sequence_no": self._events.max_sequence("run", run_id) + 1,
                "event_type": event_type,
                "event_version": 1,
                "occurred_at": envelope.occurred_at.isoformat(),
                "payload_json": payload,
                "artifact_refs_json": [],
                "trace_id": None,
            }
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
        evaluation_runs: EvaluationRunRepository | None = None,
    ) -> None:
        self._runs = runs
        self._episodes = episodes
        self._steps = steps
        self._metrics = metrics
        self._events = events
        self._evaluation_runs = evaluation_runs or EvaluationRunRepository(metrics.engine)

    def report(self, run_id: str, *, evaluation_run_id: str | None = None) -> dict[str, Any]:
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
        generations = self._evaluation_runs.for_run(run_id)
        selected_evaluation = next(
            (
                generation
                for generation in generations
                if evaluation_run_id is None or generation["evaluation_run_id"] == evaluation_run_id
            ),
            None,
        )
        if evaluation_run_id is not None and selected_evaluation is None:
            raise ValueError(
                f"evaluation run {evaluation_run_id} not found for source run {run_id}"
            )
        metrics_rows = (
            self._metrics.for_evaluation_run(selected_evaluation["evaluation_run_id"])
            if selected_evaluation is not None
            else []
        )
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
            "assistance_violated": bool(row.get("assistance_violated", 0)),
            "episodes": episodes_typed,
            "operational": {
                "provider_calls": provider_calls,
                "provider_failures": provider_failures,
                "events": len(events_rows),
                "tokens": usage_tokens,
                "cost_status": "unknown",  # GATE-009 pending: no USD claims
            },
            "metrics": [dict(m) for m in metrics_rows],
            "evaluation": (
                {
                    "evaluation_run_id": selected_evaluation["evaluation_run_id"],
                    "evaluator_id": selected_evaluation["evaluator_id"],
                    "evaluator_version": selected_evaluation["evaluator_version"],
                    "status": selected_evaluation["status"],
                }
                if selected_evaluation is not None
                else None
            ),
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
            f"- Assistance violation: **{report['assistance_violated']}**",
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
