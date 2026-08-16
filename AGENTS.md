# AGENTS.md

## Mission

Build the Zugzwang Research Kernel as an attribution-first, local-first, CLI-first system for reproducible LLM decision experiments. Chess is the first and only required domain through v0.1. Do not generalize the core ahead of evidence.

## Read order

Before modifying anything:

1. `START_HERE.md`
2. `docs/decisions/DECISIONS.yaml`
3. current milestone in `docs/roadmap/`
4. relevant requirements and accepted ADRs
5. nearest nested `AGENTS.md`
6. the most specific skill in `.agents/skills/`

## Human authority

Mestre Mael is the final human operator. A `pending` gate is not an accepted recommendation. Agents must not select license, Python support, CLI identity, retention, provider redistribution, release compatibility, paid model matrix, or other human gates.

When blocked, use `prepare-human-decision-gate` and return a bounded decision packet.

## Global invariants

- No illegal action is applied to the canonical environment.
- No committed step is executed twice on resume.
- No provider call, retry, fallback, tool call, candidate selection, or engine assistance is hidden.
- Stockfish evaluation is post-hoc unless the manifest explicitly declares an assisted regime.
- Intended and effective assistance classes `H` and `K` are persisted.
- Raw evidence is immutable; derived/public artifacts never overwrite it.
- Every run is attributable to exact manifest, code, plugin, model/provider, evaluator, dataset and pricing snapshots.
- Default tests make no network calls and spend no money.
- Core contracts do not expose SDK, SQL, CLI, concrete chess-library, or engine types.
- CLI and future API call application services; they do not contain domain/SQL logic.

## Scope discipline

Do not add Web UI, remote service, Postgres, distributed workers, RAG/vector DB, training, arbitrary code execution, or multi-game generalization before the roadmap trigger. Create an issue or ADR proposal instead.

## Work order

Every implementation change needs a `ZGW-XXXX` work order with requirements, ADRs, gates, allowed paths, evidence and stop conditions. Keep the delta minimal and produce a handoff packet.

## Skills

Use an explicit skill when applicable. Important skills include:

- `bootstrap-workspace`
- `implement-domain-contract`
- `implement-runtime-state-machine`
- `implement-provider-adapter`
- `implement-chess-environment`
- `implement-decision-strategy`
- `implement-knowledge-packet`
- `implement-multimodal-observation`
- `implement-evaluator-metric`
- `build-run-bundle`
- `design-research-experiment`
- `audit-assistance-provenance`
- `test-fault-replay`
- `architecture-boundary-review`
- `write-or-update-adr`
- `prepare-human-decision-gate`
- `code-review`
- `release-readiness`

## Commands available in this pre-scaffold corpus

```bash
python scripts/validate_foundation.py
python scripts/validate_foundation.py --strict
python scripts/decision_status.py
python scripts/new_adr.py --help
python scripts/new_experiment.py --help
```

After M0, update this file with exact `uv run` commands. Do not invent commands before they exist.

## Commands (post-M0, uv workspace)

```bash
uv sync --all-packages --all-extras --locked   # install editable workspace
uv run pytest -m "not e2e"                     # offline suite (no network/secrets/engines)
uv run ruff check .                            # lint
uv run ruff format --check .                   # format
uv run pyright                                 # strict typing
uv run zugzwang doctor                         # workspace validation
uv run zugzwang experiment validate experiments/fake-smoke.yaml
uv run zugzwang experiment plan experiments/fake-smoke.yaml
uv run zugzwang run experiments/fake-smoke.yaml
uv run zugzwang schema                         # regenerate JSON Schemas
uv run python scripts/validate_foundation.py --strict
```

## Testing

Run the smallest relevant tests first, then the full offline suite. Real-provider/engine tests require explicit opt-in, secrets and budget. Report passed, skipped and failed commands exactly.

## Documentation and traceability

Behavior change updates requirements, schemas, examples and docs in the same PR. Architecture changes require ADR. Public-contract changes require compatibility analysis. Scientific protocol changes require an experiment-card revision and cannot occur after preregistration without explicit amendment.

## Forbidden shortcuts

- accepting a recommended gate automatically;
- retrying an ambiguous provider timeout as if no work occurred;
- coercing unknown cost/usage to zero;
- storing large raw blobs directly in operational tables;
- importing concrete adapters from core;
- using SAN `+/#` or engine values without recording leakage/assistance;
- calling a smoke run a benchmark;
- deleting failed attempts or inconvenient outcomes;
- using another LLM as sole chess-fact verifier;
- broad refactors outside the work order.

## Completion report

Return:

```yaml
status: complete | partial | blocked
changed_paths: []
tests: {passed: [], skipped: [], failed: []}
requirements_satisfied: []
invariants_checked: []
decisions_needed: []
risks: []
follow_up: []
```
