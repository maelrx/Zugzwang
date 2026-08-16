# Estratégia de testes

## 1. Objetivo

O principal defeito que o Zugzwang precisa evitar não é apenas “retornar valor errado”. É produzir evidência aparentemente válida depois de corrupção, retry oculto, replay duplicado, drift de schema ou assistência mal classificada.

## 2. Camadas

| Camada | Testa | Dependências permitidas |
|---|---|---|
| Unit | value objects, reducers, policies puras | nenhuma I/O |
| Property | invariantes, roundtrips, state transitions | deterministic generators |
| Contract | ports/adapters, schemas, providers, plugins | fakes/local subprocesses |
| Integration | SQLite, CAS, migrations, runtime | temp filesystem/db |
| Fault | crash, timeout, partial write, cancellation | injected failures |
| Replay | same bundle/seed → same projections | no provider network |
| Differential | chess adapter vs reference implementation | selected rules substrate |
| Performance | writer, CAS, renderer, analytical scans | controlled machine |
| E2E opt-in | real provider/Stockfish | secrets + explicit budget |
| Scientific validation | pairing, randomization, metric code | frozen experiment corpus |

## 3. Test matrix by invariant

### Persistence

- object written, SQL not committed → orphan is safe;
- SQL ref never points to absent object;
- event and projection advance atomically;
- duplicate finalize is no-op;
- migration roundtrip on supported versions;
- WAL/SQLite version doctor rejects unsafe setup.

### Runtime

- interruption before/after `COMMITTED`;
- cancellation while provider call is in flight;
- timeout with `outcome_unknown`;
- hard budget stop before new billable call;
- concurrency respects per-provider limits;
- resume does not repeat committed action.

### Providers

- exact lowering fixture per dialect;
- unsupported capability fails preflight;
- native vs emulated output provenance;
- raw response preserved independently of normalized response;
- no SDK retry outside recorded attempt;
- usage missing/partial/streamed cases.

### Chess

- FEN/UCI roundtrip;
- legal move parity;
- castling, en passant, promotion, repetition and fifty-move;
- deterministic renderer bytes and metadata;
- opaque action mapping does not leak SAN semantics;
- geometric transformations preserve mapped expectations where valid.

### Scientific protocol

- intended/effective H and K classes;
- wrong skill/control never mislabeled;
- all conditions share frozen dataset hash;
- metric slices cannot silently mix protocols;
- result table includes uncertainty and sample count;
- public bundle redaction cannot change derived metrics undetected.

## 4. CI policy

Default CI is offline and deterministic. Real-provider and real-engine tests are opt-in, manually dispatched, secret-scoped and budget-limited. A flaky test is quarantined only with owner, issue and expiry; it never becomes accepted background noise.

## 5. Coverage

Coverage percentage is secondary. Critical reducers, state machines, migrations, assistance propagation and bundle validators require branch/path evidence. Mutation testing may be introduced selectively after M3.
