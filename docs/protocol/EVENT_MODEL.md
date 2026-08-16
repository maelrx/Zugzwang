# Event model

## Role

Events are the append-only scientific history. Projections are operational conveniences.

## Envelope

```json
{
  "event_id": "evt_01...",
  "event_type": "step_committed",
  "event_version": "1.0.0",
  "occurred_at": "2026-08-12T18:00:00Z",
  "sequence": 104,
  "run_id": "run_...",
  "condition_id": "cond_...",
  "episode_id": "ep_...",
  "step_id": "step_...",
  "attempt_id": null,
  "correlation_id": "corr_...",
  "causation_id": "evt_...",
  "payload": {},
  "artifact_refs": []
}
```

## Event families

### Lifecycle

- `run_created`
- `run_validated`
- `run_planned`
- `run_started`
- `run_paused`
- `run_resumed`
- `run_interrupted`
- `run_finalizing`
- `run_completed`
- `run_failed`
- `run_canceled`

### Episode/step

- `episode_started`
- `observation_built`
- `step_started`
- `action_proposed`
- `verification_completed`
- `step_committed`
- `episode_completed`

### Calls

- `model_call_started`
- `model_call_completed`
- `model_call_failed`
- `model_call_outcome_unknown`
- `retry_scheduled`
- `fallback_selected`

### Tools/engines

- `tool_invocation_started`
- `tool_invocation_completed`
- `tool_invocation_failed`
- `engine_evaluation_completed`

### Artifacts/metrics

- `artifact_stored`
- `metric_observed`
- `bundle_finalized`
- `bundle_imported`

### Integrity

- `protocol_violation`
- `assistance_escalated`
- `retention_redaction_applied`
- `security_policy_blocked`

## Ordering

Sequence is monotonic within a run. Wall-clock timestamps are not used to infer order.

## Payload policy

Large content is an artifact ref. Payload remains small, typed and versioned.

## Evolution

Each event type has its own version. Upcasters produce a current in-memory shape while preserving raw event bytes.

## Idempotency

Append operation uses event ID and expected sequence. Duplicate event ID is a no-op only when payload hash matches; otherwise it is an integrity error.

Machine schema: `schemas/event.schema.json`.
