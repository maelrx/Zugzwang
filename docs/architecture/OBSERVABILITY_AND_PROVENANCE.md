# Observabilidade e proveniência

## Events first

Structured domain events are canonical. Logs are a human/operator projection. OpenTelemetry is optional export.

## Event envelope

```json
{
  "event_id": "evt_...",
  "event_type": "model_call_completed",
  "event_version": "1.0.0",
  "occurred_at": "...",
  "run_id": "...",
  "episode_id": "...",
  "step_id": "...",
  "attempt_id": "...",
  "sequence": 42,
  "payload": {},
  "artifact_refs": []
}
```

## Provenance graph

Every derived object points backward:

```text
metric
→ evaluator/config
→ action/response
→ attempt
→ request
→ observation
→ source state/content/knowledge
→ manifest and plugin snapshots
```

## Logs

- JSON structured;
- no raw secrets;
- run/episode/step IDs;
- stable event/error names;
- human pretty output separate.

## OTel

Opt-in and disabled by default. Export spans for performance, not as the only evidence source. Provider framework span attributes are not part of the Zugzwang public contract.

## Cost

Store provider-reported usage and locally estimated cost separately. Pricing snapshots include source, currency, effective date and stale status.

## Clock

Use UTC wall time for audit and monotonic time for durations.
