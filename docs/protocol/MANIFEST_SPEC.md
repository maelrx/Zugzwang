# Manifest specification

## Purpose

The source manifest is human-authored intent. The resolved manifest is the immutable executable protocol.

```text
manifest.source.yaml
→ strict validation
→ plugin/capability/default/price resolution
→ manifest.resolved.json
→ canonical serialization
→ protocol fingerprint
```

## Source principles

- YAML is data only;
- unknown fields fail;
- no Python expressions;
- no implicit environment interpolation;
- secrets are references, not values;
- paths resolve relative to manifest;
- patches are recorded;
- defaults are visible after resolution.

## Top-level draft

```yaml
schema_version: "0.1.0"

experiment:
  id: rep-001
  title: Representation Matrix
  description: ...
  tags: [representation, multimodal]

task:
  plugin: chess.move_selection
  version: "0.1"
  suite: suite://zugzwang/rep-v1

factors:
  mode: product
  dimensions:
    observation: [fen, image, fen_image]
    model: [model-a]

strategy:
  plugin: strategy.direct
  version: "0.1"
  regime: R0

provider:
  plugin: provider.openai_compatible
  model: exact-model-id
  endpoint_ref: local-default
  capabilities:
    required: [text_input]
    preferred: [usage_reporting]
    on_unsupported: fail

protocol:
  assistance:
    declared_h: H2
    declared_k: K0
  output:
    action_notation: uci
    schema: chess_move_v1
  retries:
    transport: 1
    parse: 0
    illegal: 0
    strategic: 0

budget:
  max_calls: 1000
  max_cost_usd: 10
  per_call_timeout_seconds: 120

evaluation:
  live: []
  posthoc:
    - plugin: evaluator.stockfish
      metric_set: move_quality_v1
      config_ref: stockfish-depth-18

artifacts:
  retention_policy: full-research
  bundle: true

runtime:
  concurrency: 4
  seed: 42
```

## Resolved fields

Resolution adds:

- plugin distribution/version;
- exact capability report;
- normalized paths;
- environment/runtime snapshot;
- pricing snapshot;
- content and knowledge hashes;
- expanded conditions;
- derived budgets;
- defaults;
- warnings;
- resolution timestamp.

The resolved manifest never contains secret values.

## Factor expansion

### Product

Cartesian product with deterministic ordering.

### Zip

Position-wise pairing; dimensions must have equal length.

### IDs

Condition ID derives from canonical factor payload plus protocol fingerprint. Display names are not identity.

## Patches

CLI patches use JSON Pointer-like paths and are appended to an immutable patch log. The final resolved artifact includes source hash and ordered patches.

## Validation phases

1. syntax;
2. schema;
3. cross-field invariants;
4. plugin availability;
5. capability resolution;
6. assistance compatibility;
7. budget feasibility;
8. suite/data availability;
9. human decision gates;
10. plan construction.

## Versioning

`schema_version` follows its own semantic version. Unknown major versions fail. Minor versions require a compatible reader/upcaster.

Machine schema: `schemas/experiment-manifest.schema.json`.
