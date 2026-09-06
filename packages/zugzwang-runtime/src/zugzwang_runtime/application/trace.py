"""Read-only reconstruction of one live decision and its post-hoc evidence."""

from __future__ import annotations

import json
from contextlib import suppress
from typing import Any

from zugzwang_core.domain.artifacts import ArtifactRef

from ..artifacts.cas import ContentAddressedStore
from ..persistence.repositories import (
    AttemptRepository,
    EvaluationRunRepository,
    EventRepository,
    MetricObservationRepository,
    RunRepository,
    StepRepository,
)


class TraceStepService:
    """Returns the evidence graph for a step without executing anything."""

    def __init__(
        self,
        *,
        runs: RunRepository,
        steps: StepRepository,
        attempts: AttemptRepository,
        events: EventRepository,
        metrics: MetricObservationRepository,
        cas: ContentAddressedStore,
        evaluation_runs: EvaluationRunRepository | None = None,
    ) -> None:
        self._runs = runs
        self._steps = steps
        self._attempts = attempts
        self._events = events
        self._metrics = metrics
        self._cas = cas
        self._evaluation_runs = evaluation_runs or EvaluationRunRepository(metrics.engine)

    def trace(self, step_id: str) -> dict[str, Any]:
        step = self._steps.get(step_id)
        if step is None:
            raise ValueError(f"step {step_id} not found")
        episode_id = str(step["episode_id"])
        attempts = self._attempts.for_step(step_id)
        events = self._events.for_step(step_id)
        run_id = str(events[0]["run_id"]) if events else ""
        live_decision = {
            "step": dict(step),
            "observation": self._read_ref(step.get("observation_artifact_id")),
            "decision_trace": self._read_ref(step.get("decision_trace_artifact_id")),
            "attempts": [
                {
                    **dict(attempt),
                    "request": self._read_ref(attempt.get("request_artifact_id")),
                    "wire_request": self._read_ref(attempt.get("wire_request_artifact_id")),
                    "wire_response": self._read_ref(attempt.get("wire_response_artifact_id")),
                    "response": self._read_ref(attempt.get("response_artifact_id")),
                    "reasoning_telemetry": self._read_ref(
                        attempt.get("reasoning_telemetry_artifact_id")
                    ),
                }
                for attempt in attempts
            ],
            "events": [self._event_json(event) for event in events],
        }
        generations = self._evaluation_runs.for_run(run_id) if run_id else []
        selected_generation = next(
            (generation for generation in generations if generation["status"] == "COMPLETED"),
            None,
        )
        metrics = (
            self._metrics.for_evaluation_run(selected_generation["evaluation_run_id"])
            if selected_generation is not None
            else []
        )
        return {
            "step_id": step_id,
            "run_id": run_id,
            "episode_id": episode_id,
            "live_decision": live_decision,
            "post_hoc_evaluation": {
                "metrics": [dict(metric) for metric in metrics if metric.get("step_id") == step_id],
                "generations": [
                    {
                        "evaluation_run_id": generation["evaluation_run_id"],
                        "evaluator_id": generation["evaluator_id"],
                        "evaluator_version": generation["evaluator_version"],
                        "status": generation["status"],
                    }
                    for generation in generations
                ],
                "selected_evaluation_run_id": (
                    selected_generation["evaluation_run_id"]
                    if selected_generation is not None
                    else None
                ),
                "note": "These artifacts are post-hoc and are not readable by SearchWorkspace.",
            },
        }

    def _read_ref(self, ref_raw: Any) -> Any:
        if not isinstance(ref_raw, str) or not ref_raw.startswith("sha256:"):
            return None
        try:
            payload = self._cas.get(ArtifactRef.parse(ref_raw))
            return json.loads(payload.data.decode("utf-8"))
        except Exception:
            return {"artifact_ref": ref_raw, "available": False}

    @staticmethod
    def _event_json(event: dict[str, Any]) -> dict[str, Any]:
        payload = dict(event)
        if isinstance(payload.get("payload_json"), str):
            with suppress(json.JSONDecodeError):
                payload["payload_json"] = json.loads(payload["payload_json"])
        if isinstance(payload.get("artifact_refs_json"), str):
            with suppress(json.JSONDecodeError):
                payload["artifact_refs_json"] = json.loads(payload["artifact_refs_json"])
        return payload
