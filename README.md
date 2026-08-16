<div align="center">

# ♟ Zugzwang Research Kernel

**An attribution-first execution kernel for verifiable LLM decision experiments.**

[![Status: v0.1 kernel](https://img.shields.io/badge/status-v0.1%20kernel-4C956C.svg)](#project-status)
[![Interface: CLI first](https://img.shields.io/badge/interface-CLI--first-2F6F9F.svg)](docs/architecture/SYSTEM_DESIGN.md)
[![Architecture: Modular Monolith](https://img.shields.io/badge/architecture-modular%20monolith-4C956C.svg)](docs/architecture/MASTER_TECHNICAL_DESIGN.md)
[![Python: 3.13 and 3.14 proposed](https://img.shields.io/badge/python-3.13%20%7C%203.14-3776AB.svg?logo=python&logoColor=white)](docs/decisions/HUMAN_DECISION_GATES.pt-BR.md)
[![Workspace: uv](https://img.shields.io/badge/workspace-uv-DE5FE9.svg)](docs/architecture/REPOSITORY_LAYOUT.md)
[![Validation: Pydantic](https://img.shields.io/badge/contracts-Pydantic%20strict-E92063.svg?logo=pydantic&logoColor=white)](docs/protocol/MANIFEST_SPEC.md)
[![Runtime: asyncio](https://img.shields.io/badge/runtime-asyncio-3776AB.svg)](docs/architecture/RUNTIME_AND_STATE_MACHINES.md)
[![Database: SQLite WAL](https://img.shields.io/badge/database-SQLite%20WAL-003B57.svg?logo=sqlite&logoColor=white)](docs/architecture/DATA_ARCHITECTURE.md)
[![Analytics: DuckDB + Parquet](https://img.shields.io/badge/analytics-DuckDB%20%2B%20Parquet-FFF000.svg)](docs/architecture/DATA_ARCHITECTURE.md)
[![Providers: Agnostic](https://img.shields.io/badge/providers-agnostic-555.svg)](docs/architecture/PROVIDER_ARCHITECTURE.md)
[![Science: Reproducible](https://img.shields.io/badge/science-reproducible-1B998B.svg)](docs/research/CLAIMS_AND_EVIDENCE_POLICY.md)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-2F6F9F.svg)](LICENSE)

[Português](README.pt-BR.md) · [Start here](START_HERE.md) · [Documentation index](docs/INDEX.md) · [Decision console](docs/decisions/HUMAN_DECISION_GATES.pt-BR.md) · [Roadmap](docs/roadmap/ROADMAP.md)

</div>

> [!IMPORTANT]
> v0.1 of the kernel is implemented: uv workspace, core/runtime/chess/cli packages, SQLite+WAL, CAS, durable runs with interrupt/resume, R0-R3 strategies, two provider adapters, post-hoc Stockfish evaluation (fake UCI offline), bundles, Parquet/DuckDB and an offline scientific suite. Human gates GATE-001/002/004 are ratified (GPL-3.0-or-later, Python >=3.13, `zugzwang` + `zgw`); the remaining gates keep conservative defaults (fake-only execution, no USD claims, no public redistribution).

## Quick start

```bash
uv sync --all-packages --locked   # editable workspace install
zugzwang init                     # create a local .zugzwang workspace
zugzwang doctor                   # validate workspace, DB, plugins, engine
zugzwang run experiments/fake-smoke.yaml --workspace .
zugzwang runs list --workspace .
zugzwang evaluate <run-id> --workspace .    # post-hoc, fake UCI engine
zugzwang report <run-id> --workspace .
zugzwang export <run-id> --output bundle/ --workspace .
uv run pytest -m "not e2e"       # offline suite: no network, no secrets
```

See [docs/research/V0_1_FAKE_SUITE.md](docs/research/V0_1_FAKE_SUITE.md) for the
scientific suite and what its results do — and do not — measure.

## The thesis

“An LLM playing chess” is not one capability. Observed performance is a compound of state representation, rule tracking, legal action grounding, candidate generation, search, value estimation, memory, formatting, retries, tools, and external assistance.

Zugzwang exists to make those components explicit.

The kernel answers a stricter question than “which model won?”:

> **Which component supplied which share of the observed capability, under which representation, knowledge, assistance, budget, distribution, and failure policy?**

Chess is the first domain because it supplies a deterministic state machine, formally checkable actions, long trajectories, automatic evaluation, adversarial distributions, and a mature ecosystem of engines and human data. The long-term abstraction is a research kernel for verifiable sequential decision systems, but the first implementation remains deliberately chess-first.

## What Zugzwang is

Zugzwang is a local-first, CLI-first, provider-agnostic kernel for:

- declaring experiments through strict, versioned manifests;
- resolving a source manifest into an immutable execution plan;
- running model, strategy, environment, tool, verifier, and evaluator components behind explicit contracts;
- recording every attempt, retry, tool call, artifact, transition, metric, cost, and protocol deviation;
- resuming interrupted runs without replaying committed actions;
- exporting self-contained, checksummed run bundles;
- re-evaluating bundles offline with versioned metrics;
- comparing systems without laundering harness or engine competence into the model.

## What Zugzwang is not

The initial kernel is not:

- a chess bot product;
- a Stockfish wrapper;
- a public arena or a single Elo leaderboard;
- a universal agent framework;
- a model training platform;
- a hosted multi-user service;
- a Web UI;
- a hidden retry, routing, or fallback layer.

Those may become adapters, plugins, or separate products. None may redefine the scientific semantics of the kernel.

## Scientific coordinate system

Every condition is described across independent axes.

| Axis | Question | Initial vocabulary |
|---|---|---|
| Inference regime `R` | How is the decision produced? | `R0` direct, `R1` grounded, `R2` repair, `R3` structured |
| Operational assistance `H` | What formal or strategic help was supplied live? | `H0` parser through `H7` engine-selected action |
| Knowledge assistance `K` | What external knowledge entered the prompt or policy? | `K0` none through `K7` current-position expert analysis |
| Observation profile | How was state represented? | FEN, ASCII, PGN/history, image, redundant, conflicting |
| Budget | How much compute was available? | calls, tokens, time, cost, candidates, retries |
| Distribution | Where did the state come from? | IID human, temporal, random-legal, geometric, synthetic, Chess960 later |

A run declares intended classes. The event stream records what actually happened. If a tool raises effective assistance above the declaration, the run is marked as a protocol violation rather than silently reported as stronger.

## The first scientific program

The v0.1 experiment program begins with paired local-decision studies before expensive full-game claims.

| Experiment | Core question |
|---|---|
| `REP-001` | Which state representation best separates perception, tracking, and decision quality? |
| `GROUND-001` | Does reasoning before legal-action grounding outperform legal moves shown from the start? |
| `SKILL-001` | Does a correct expert knowledge packet help beyond persona, irrelevant text, and a plausible but wrong skill? |
| `MM-001` | Does a redundant board image improve spatial reasoning when a perfect symbolic state is already present? |
| `MM-002` | Which modality does a model trust when image and symbolic state conflict? |
| `DEMO-001` | Are a few semantically matched demonstrations more useful than many random demonstrations at equal token budget? |

See [Experiment Catalog v0.1](docs/research/EXPERIMENT_CATALOG_V0_1.md).

## System architecture

```mermaid
flowchart LR
    CLI[CLI adapter] --> APP[Application services]
    APP --> PLAN[Manifest resolver and planner]
    PLAN --> RUN[Durable local runtime]

    RUN --> ENV[Environment port]
    RUN --> STRAT[Decision strategy port]
    RUN --> PROV[Model backend port]
    RUN --> TOOL[Tool and verifier ports]
    RUN --> EVAL[Evaluator port]
    RUN --> PERSIST[Persistence ports]

    PERSIST --> SQL[(SQLite WAL)]
    PERSIST --> CAS[(Content-addressed artifacts)]
    PERSIST --> PARQ[(Parquet exports)]

    PARQ --> DUCK[DuckDB analysis]
    APP -. same services later .-> API[Future API adapter]
    API -. optional later .-> WEB[Future Web UI]
```

The recommended implementation is a modular monolith with hexagonal boundaries:

```text
zugzwang-core
    ↑
zugzwang-runtime
    ↑             ↖
zugzwang-cli       plugins/*
    ↑             ↗
zugzwang-chess
```

The core does not import a provider SDK, SQLAlchemy, Typer, a concrete chess library, or Stockfish. Provider SDK types do not cross adapter boundaries. Plugins do not receive database sessions. The CLI never executes SQL.

## Data architecture

Three data planes solve three different problems:

| Plane | Recommended substrate | Purpose |
|---|---|---|
| Operational | SQLite in WAL mode | current state, checkpoints, budgets, projections |
| Evidence | filesystem CAS, SHA-256, Zstandard | prompts, responses, images, traces, snapshots |
| Analytical | Parquet queried by DuckDB | comparison, statistics, reports, downstream notebooks |

The scientific product is the portable run bundle, not the local database.

```text
run-bundle/
├── bundle.json
├── manifest.source.yaml
├── manifest.resolved.json
├── runtime-snapshot.json
├── plugin-snapshot.json
├── pricing-snapshot.json
├── events.jsonl.zst
├── artifacts/
├── episodes.parquet
├── attempts.parquet
├── metrics.parquet
├── games.pgn
└── checksums.sha256
```

## Provider architecture

Zugzwang owns a narrow canonical `ModelBackend` contract. A backend performs one model inference. It does not secretly implement memory, retries, tools, fallback, routing, search, or an agent loop.

Initial adapters:

- Pydantic AI Direct Model Requests, used as a transport and schema translation substrate;
- a direct OpenAI-compatible HTTP adapter for local servers and dialect testing;
- a deterministic fake backend for offline tests;
- optional bridges such as LiteLLM only as explicit plugins.

Capabilities are negotiated rather than assumed: structured output, images, tools, usage metadata, reasoning control, logprobs, seed support, prompt caching, streaming, and idempotency are recorded per backend and model snapshot.

## Multimodal and knowledge-ready, without premature RAG

The core request model uses typed content parts:

```text
TextPart
ImageArtifactPart
StructuredStatePart
ToolResultPart
```

Images are immutable CAS artifacts with content hash, MIME type, dimensions, renderer version, board orientation, theme, and source state hash. This makes visual experiments reproducible and allows cross-modal conflict to be intentional rather than accidental.

Static expert knowledge enters through versioned `KnowledgePacket` artifacts. This supports `SKILL-001` without installing a vector database or retrieval pipeline. Position-conditioned retrieval remains a later, separately classified regime.

## Project status

The foundation pack is complete enough to start the scaffold, but several human-owned decisions deliberately block irreversible code choices:

1. license and chess rules substrate;
2. Python support floor;
3. default raw prompt/response retention;
4. final CLI command name;
5. redistribution policy for provider outputs;
6. Stockfish acquisition and redistribution;
7. initial plugin API stability;
8. first-release variant scope;
9. cost registry governance;
10. documentation language policy;
11. inaugural paid model/budget matrix;
12. package publication topology.

See the [Mestre Mael Decision Console](docs/decisions/HUMAN_DECISION_GATES.pt-BR.md).

## Repository map

```text
.
├── AGENTS.md
├── .agents/skills/              # reusable Codex engineering workflows
├── docs/
│   ├── product/
│   ├── research/
│   ├── architecture/
│   ├── requirements/
│   ├── protocol/
│   ├── engineering/
│   ├── roadmap/
│   ├── decisions/
│   └── adr/
├── schemas/                     # draft machine-readable contracts
├── examples/
│   ├── experiments/
│   └── knowledge-packets/
├── packages/                    # package boundaries and nested AGENTS.md
├── plugins/                     # plugin boundaries and nested AGENTS.md
├── scripts/                     # documentation and contract validators
├── archive/source-material/     # supplied research and original design inputs
└── .github/                     # contribution templates and docs CI
```

## Starting the scaffold

Do not implement around unresolved gates. The intended sequence is:

```bash
# 1. Read the operating map
cat START_HERE.md
cat docs/decisions/HUMAN_DECISION_GATES.pt-BR.md

# 2. Record human decisions
# Edit docs/decisions/DECISIONS.yaml and the affected ADR status.

# 3. Validate the documentation corpus
python scripts/validate_foundation.py

# 4. Start M0 with the Codex workflow
# Explicitly invoke the bootstrap-workspace skill.
```

No `uv.lock` is included because dependency resolution should occur only after the Python and licensing gates are ratified. The proposed workspace templates are documented, not falsely presented as an implemented runtime.

## Quality policy

A result is not publishable unless it records:

- exact model/provider identifier and date;
- complete source and resolved manifests;
- prompt and representation hashes;
- retry, fallback, routing, and selection policy;
- declared and effective `H` and `K` classes;
- raw or policy-compliant evidence artifacts;
- engine version and exact evaluation budget;
- costs, tokens, latency, failures, and timeouts;
- parsing errors separately from illegal actions;
- legal blunders separately from protocol failures;
- distribution, seeds, paired conditions, and uncertainty;
- code, plugin, schema, and metric versions.

See [Claims and Evidence Policy](docs/research/CLAIMS_AND_EVIDENCE_POLICY.md).

## Documentation

- [Documentation index](docs/INDEX.md)
- [Product requirements](docs/product/PRODUCT_REQUIREMENTS.md)
- [Scientific foundations](docs/research/SCIENTIFIC_FOUNDATIONS.md)
- [Master technical design](docs/architecture/MASTER_TECHNICAL_DESIGN.md)
- [System design](docs/architecture/SYSTEM_DESIGN.md)
- [Functional requirements](docs/requirements/FUNCTIONAL_REQUIREMENTS.md)
- [Protocol taxonomy](docs/research/PROTOCOL_TAXONOMY.md)
- [ADRs](docs/adr/README.md)
- [Roadmap](docs/roadmap/ROADMAP.md)
- [Test strategy](docs/engineering/TEST_STRATEGY.md)
- [Codex agent operating model](docs/engineering/CODEX_AGENT_OPERATING_MODEL.md)

## Contributing

The project is designed for research engineers, model authors, benchmark maintainers, chess tooling developers, and reproducibility reviewers. Read [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md), and the root [AGENTS.md](AGENTS.md) before proposing code.

## License

A license has intentionally not been selected in this foundation pack. The choice is coupled to the chess rules substrate and downstream embedding strategy. Until [ADR-004](docs/adr/ADR-004-licenca-e-biblioteca-de-regras.md) is accepted and a `LICENSE` file is committed, the repository should not be advertised as legally open source.

## Citation

A `CITATION.cff` foundation file is included. Published research should cite both the Zugzwang release and the primary papers whose datasets, protocols, or methods it uses.

---

**Chess first. Attribution always.**
