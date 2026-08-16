# Layout do repositório

## Proposed tree

```text
.
├── pyproject.toml
├── uv.lock                         # generated after gates
├── AGENTS.md
├── .agents/skills/
├── packages/
│   ├── zugzwang-core/
│   ├── zugzwang-runtime/
│   ├── zugzwang-chess/
│   └── zugzwang-cli/
├── plugins/
│   ├── provider-pydantic-ai/
│   ├── provider-openai-compatible/
│   ├── evaluator-stockfish/
│   └── reporter-parquet/
├── schemas/
├── examples/
├── docs/
├── tests/
└── dev/
```

## Why a uv workspace

A workspace gives each package an independent `pyproject.toml` while sharing a single lockfile and development environment. It suits core/CLI separation, plugins, and a possible Rust extension. It does not enforce import isolation by itself, so architecture tests remain mandatory.

Reference: [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/).

## Package granularity

Do not create distributions for every folder. Separate a package only when it has at least one of:

- optional heavyweight dependencies;
- distinct release cadence;
- meaningful public import boundary;
- native build;
- plugin deployment;
- ability to test/install independently.

## Root project

Recommended root:

- non-package workspace coordinator;
- shared dependency groups;
- tool configuration;
- no runtime imports;
- `requires-python` ratified by GATE-002.

## Lockfile

Generate `uv.lock` only after human gates. Commit it. Export CycloneDX or PEP 751 artifacts in release CI.

## Nested instructions

Each package/plugin receives an `AGENTS.md` with local boundary rules. Root guidance remains short enough for Codex’s default instruction budget.
