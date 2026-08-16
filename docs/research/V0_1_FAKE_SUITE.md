# v0.1 fake scientific suite

The `experiments/` directory contains the offline scientific suite of v0.1.
Every experiment runs against the deterministic fake backend — no network,
no secrets, no engines. This suite proves the protocol machinery; it proves
nothing about real models.

## Suite contents

| Manifest | Task | What it measures |
|---|---|---|
| `fake-smoke.yaml` | counter | the full durable machinery (M0 vertical slice) |
| `chess-move-selection.yaml` | move selection (R0) | one fixed position, one model move |
| `chess-full-game.yaml` | full game | model (white) vs random-legal, capped plies |
| `strategy-suite.yaml` | move selection | R0/R1/R2/R3 over the SAME fake backend — protocol differences only |
| `paired-openings.yaml` | full game | 2 openings x 2 colors (FR-030), paired structure |
| `state-reconstruction.yaml` | reconstruction | FEN prediction scored by exact/piece-square/auxiliary accuracy |

## How to run

```bash
uv sync --all-packages --locked
zugzwang init
zugzwang run experiments/strategy-suite.yaml --workspace .
zugzwang runs list --workspace .
zugzwang evaluate <run-id> --workspace .          # fake UCI engine, post-hoc
zugzwang report <run-id> --workspace .
zugzwang export <run-id> --output bundle/ --workspace .
```

## What these results measure

- protocol correctness: parsing, legality, transitions, events, persistence;
- strategy mechanics: R0 raw output, R1 grounding, R2 formal repair, R3
  structured proposals;
- attribution machinery: declared vs effective assistance, attempts, budgets;
- portability: bundles, checksums, offline re-evaluation.

## What they do NOT measure

- any capability of any real model — the backend is scripted;
- strength or quality of moves — the fake never reasons;
- economic cost — cost status is `unknown` until GATE-009 is ratified;
- system-level claims — a smoke run is never a benchmark.

Per the project's scientific policy, no result from this suite may be
reported as a model capability claim (CLAIMS_AND_EVIDENCE_POLICY).
