# Domínio de xadrez

## 1. Canonical state

A complete game state includes:

- piece placement;
- side to move;
- castling rights;
- en passant target;
- halfmove clock;
- fullmove number;
- repetition history or sufficient key history;
- terminal status;
- optional synthetic clock.

FEN is an observation encoding, not the entire identity of a trajectory.

## 2. Canonical action

Persist UCI:

```text
e2e4
e7e8q
```

SAN is an optional representation and may carry semantic leakage.

## 3. Environment ports

```python
class ChessEnvironment(Environment[ChessState, ChessAction, ChessObservation]):
    def initial_state(...)
    def observe(...)
    def legal_actions(...)
    def transition(...)
    def outcome(...)
```

## 4. Tasks

### MoveSelection

Given canonical state, choose one action.

### StateReconstruction

Given history or visual changes, produce state components.

### LegalActionGeneration

Enumerate or classify affordances.

### CandidateRanking

Rank supplied actions without engine live.

### FullGame

Maintain a policy-induced trajectory.

### ClaimVerification

Check atomic board/tactical claims.

## 5. Rules substrate gate

The rules implementation is coupled to license:

- permissive substrate and Apache-2.0 recommendation;
- or `python-chess` and GPL strategy.

Do not wrap a dependency before ADR-004 is accepted.

## 6. Renderers

Deterministic renderers:

- FEN;
- ASCII;
- structured JSON;
- board image;
- PGN/history.

Each renderer has ID/version and artifact hash.

## 7. UCI boundary

Engines run as external subprocesses:

- explicit executable path;
- binary hash;
- version;
- options;
- NNUE hash;
- resource limits;
- transcript policy.

## 8. Standard chess first

Chess960 and variants remain test targets in research, but happy-path implementation is standard chess until GATE-008/ADR-042.

## 9. RulesKernel and delayed legality

`StandardChessRulesKernel` is the formal adapter over python-chess. The runtime
does not put a delayed legal-action list into the model observation. A
`LegalityGateway` lease decides whether a phase receives binary validation,
reason categories or enumeration. The canonical executor validates again
before committing the move.
