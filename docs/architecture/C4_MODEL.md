# C4 model

## Level 1: system context

```mermaid
flowchart LR
    Researcher[Researcher] --> Z[Zugzwang]
    Maintainer[Plugin maintainer] --> Z
    Reviewer[Reproducibility reviewer] --> Bundles[Run bundles]
    Z --> Models[Model providers]
    Z --> Engines[UCI engines]
    Z --> Bundles
    Z --> LocalFS[Local filesystem]
```

## Level 2: containers

```mermaid
flowchart TB
    CLI[CLI process] --> APP[Application layer]
    APP --> CORE[Domain core]
    APP --> EXEC[Execution runtime]
    EXEC --> PLUG[Plugin adapters]
    EXEC --> PERSIST[Persistence adapters]
    PERSIST --> SQL[(SQLite)]
    PERSIST --> CAS[(CAS)]
    PERSIST --> PQ[(Parquet)]
    PLUG --> REMOTE[Remote APIs]
    PLUG --> LOCAL[Local inference]
    PLUG --> UCI[UCI engine]
```

## Level 3: core components

```mermaid
flowchart LR
    MAN[Manifest] --> RES[Resolver]
    RES --> PLAN[Planner]
    PLAN --> RUN[Run executor]
    RUN --> SCHED[Episode scheduler]
    SCHED --> STEP[Step executor]
    STEP --> STRAT[Decision strategy]
    STRAT --> BACK[Model backend]
    STRAT --> TOOL[Tools/verifiers]
    STEP --> ENV[Environment]
    STEP --> EVT[Event collector]
    EVT --> WRITER[Persistence writer]
    WRITER --> STORE[Repositories and CAS]
    STORE --> FINAL[Bundle finalizer]
```

## Level 4 guidance

Code-level diagrams belong beside implementation after M0. The repository must not freeze class diagrams before contracts are tested. Public protocols and state machines are more stable than internal class names.
