# KnowledgePacket specification

## Purpose

Represent static external chess knowledge as a first-class, versioned artifact.

## Draft

```yaml
schema_version: "0.1.0"
packet:
  id: chess.iqp.plans
  version: "1.0.0"
  title: Isolated queen pawn plans
  language: en
  knowledge_class: K4
  scope:
    domain: chess
    phases: [middlegame]
    structures: [isolated_queen_pawn]
  applicability:
    required_features:
      - isolated_d_pawn
    contraindications:
      - immediate_forced_tactic
  content:
    principles:
      - ...
    candidate_plans:
      - ...
    failure_modes:
      - ...
  leakage:
    current_position_analysis: false
    target_move: false
    engine_evaluation: false
    transposition_lookup: false
  provenance:
    kind: curated_synthesis
    curator: ...
    sources: []
    license: ...
    created_at: ...
```

## Invariants

- packet content immutable per version;
- content hash stored;
- K class consistent with leakage;
- `K4` cannot contain current target move/eval;
- source/license required for redistribution;
- token count computed after rendering;
- rendering template versioned;
- applicability matcher versioned.

## Controls

Experiment construction supports:

- correct packet;
- wrong but plausible packet;
- irrelevant packet;
- subtly false packet;
- persona-only;
- K7 positive control.

## Security

Packets are quoted data. They cannot define tools, change system authority, interpolate secrets or contain executable templates.

Machine schema: `schemas/knowledge-packet.schema.json`.
