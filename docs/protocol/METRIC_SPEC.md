# Metric specification

## Descriptor

```yaml
metric_id: chess.wdl_loss
metric_version: "1.0.0"
value_type: float
unit: probability
direction: lower_is_better
scope: step
dimensions:
  - phase
  - condition
evaluator:
  id: stockfish
  version: ...
```

## Observation

```json
{
  "metric_id": "chess.wdl_loss",
  "metric_version": "1.0.0",
  "subject_ref": "step_...",
  "value": 0.12,
  "unit": "probability",
  "dimensions": {},
  "evaluator_id": "stockfish",
  "evaluator_version": "17",
  "config_hash": "sha256:...",
  "source_artifacts": []
}
```

## Rules

- immutable;
- append by version;
- null means unknown, not zero;
- units explicit;
- direction explicit;
- aggregation not embedded in raw observation;
- evaluator provenance required;
- live metric declares assistance impact;
- post-hoc metric declares no trajectory effect.

## Initial registry

- `protocol.parse_success`;
- `protocol.legal_first_attempt`;
- `protocol.final_valid`;
- `protocol.attempt_count`;
- `system.input_tokens`;
- `system.output_tokens`;
- `system.latency_ms`;
- `system.cost_usd_estimated`;
- `chess.state_exact`;
- `chess.affordance_distance`;
- `chess.engine_rank`;
- `chess.cp_loss_clipped`;
- `chess.wdl_loss`;
- `research.protocol_violation`;
- `research.authority_compliance`.
