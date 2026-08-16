# Domain model

## Aggregate hierarchy

```text
ExperimentDefinition
└── Run
    ├── ResolvedManifest
    ├── ExecutionPlan
    ├── Condition[]
    └── Episode[]
        └── Step[]
            ├── Observation
            ├── Attempt[]
            │   ├── ModelCall[]
            │   ├── ToolInvocation[]
            │   ├── Candidate[]
            │   └── Verification[]
            ├── CommittedAction?
            ├── Transition?
            └── MetricObservation[]
```

## Key entities

### ExperimentDefinition

Human-authored intent plus factor matrix and suite references. Mutable as a source file, immutable once resolved into a run.

### Run

Execution instance with immutable resolved manifest, lifecycle, budgets, snapshots and bundle identity.

### Condition

One factor combination. Conditions are scientific identities, not labels.

### Episode

An independent trajectory: position task, puzzle, state sequence or game.

### Step

One environment decision boundary. `COMMITTED` means the action was atomically accepted and must not be repeated on resume.

### Attempt

A proposal cycle. Parse retry, legality repair and strategic second sample are distinct attempt kinds.

### ModelCall

One canonical request sent to one backend. Stores normalized and raw evidence references, usage, latency and outcome state.

### Observation

Content parts presented to the strategy, with source, authority and artifact hashes.

### Candidate

Canonical proposed action plus rationale/claims and origin.

### Verification

Verdict from parser, rules, membership, claim checker or engine, each with assistance impact.

### MetricObservation

Versioned derived measurement with evaluator and config provenance.

## Value objects

- `RunId`, `EpisodeId`, `StepId`, `AttemptId`;
- `ContentHash`;
- `ModelRef`;
- `CapabilityReport`;
- `InferenceBudget`;
- `AssistanceProfile`;
- `KnowledgeProfile`;
- `ObservationProfile`;
- `ArtifactRef`;
- `MetricKey`;
- `ProtocolFingerprint`.

## Invariants

1. No illegal action is applied.
2. A committed step has exactly one canonical action.
3. A model call belongs to exactly one attempt.
4. Every external byte used in inference has artifact provenance or a documented non-retention policy.
5. Effective H/K cannot be lower than observed impacts.
6. Resolved manifest is immutable.
7. Metrics never overwrite a previous version.
8. Imported bundles are read-only evidence until verified.
9. IDs are stable and non-secret.
10. Secrets never enter domain objects or bundles.
