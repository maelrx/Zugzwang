# Bootstrap backlog

Backlog inicial ordenado por dependência. IDs são estáveis e podem virar GitHub Issues sem renomear o trabalho.

| ID | Tarefa | Milestone | Pri. | Depende de | Aceitação |
|---|---|---|---|---|---|
| `ZGW-0001` | Ratificar GATE-001 | M0 | P0 | `none` | Decision record e ADR-004 accepted |
| `ZGW-0002` | Ratificar GATE-002 | M0 | P0 | `none` | Python matrix recorded |
| `ZGW-0003` | Ratificar GATE-004 | M0 | P0 | `none` | CLI name recorded |
| `ZGW-0004` | Criar uv workspace | M0 | P0 | `0001,0002` | Lockfile e package graph válidos |
| `ZGW-0005` | Configurar lint/type/test tooling | M0 | P0 | `0004` | Offline CI baseline verde |
| `ZGW-0006` | Implementar canonical IDs | M0 | P0 | `0004` | Stable serialization/property tests |
| `ZGW-0007` | Implementar clock e timestamps UTC | M0 | P1 | `0004` | Injected clock; no naive datetime |
| `ZGW-0008` | Implementar usage e money types | M0 | P1 | `0004` | Decimal/unknown semantics tested |
| `ZGW-0009` | Implementar error taxonomy | M0 | P0 | `0004` | Machine codes and causes |
| `ZGW-0010` | Implementar source manifest models | M0 | P0 | `0005-0009` | Strict validation and JSON Schema |
| `ZGW-0011` | Implementar manifest resolver | M0 | P0 | `0010` | Immutable resolved manifest |
| `ZGW-0012` | Implementar canonical hashing | M0 | P0 | `0011` | Order/whitespace independent hashes |
| `ZGW-0013` | Implementar fake environment | M0 | P0 | `0006,0009` | One-step deterministic task |
| `ZGW-0014` | Implementar fake model backend | M0 | P0 | `0008,0009` | Fixture-driven requests/responses |
| `ZGW-0015` | Implementar fake evaluator | M0 | P1 | `0006` | Versioned metric fixture |
| `ZGW-0016` | Implementar CLI validate/plan | M0 | P0 | `0011-0015` | JSON and human output modes |
| `ZGW-0017` | Adicionar architecture tests | M0 | P0 | `0004` | Forbidden imports fail CI |
| `ZGW-0018` | Vertical slice fake M0 | M0 | P0 | `0012-0017` | One run produces evidence |
| `ZGW-0019` | Modelar run state machine | M1 | P0 | `0018` | Transition table exhaustive |
| `ZGW-0020` | Modelar episode/step/attempt | M1 | P0 | `0019` | Commit boundary explicit |
| `ZGW-0021` | Criar migrations SQLite | M1 | P0 | `0020` | Upgrade/downgrade smoke tests |
| `ZGW-0022` | Implementar single writer | M1 | P0 | `0021` | Bounded queue and backpressure |
| `ZGW-0023` | Implementar CAS atômico | M1 | P0 | `0020` | Hash, fsync/rename, GC roots |
| `ZGW-0024` | Implementar event store + projections | M1 | P0 | `0021-0023` | Same-transaction invariant |
| `ZGW-0025` | Implementar budget ledger | M1 | P0 | `0020,0024` | Hard stops and reservations |
| `ZGW-0026` | Implementar cancellation/checkpoint | M1 | P0 | `0022-0025` | SIGINT leaves diagnosable state |
| `ZGW-0027` | Implementar resume planner | M1 | P0 | `0026` | No committed action replay |
| `ZGW-0028` | Implementar bundle mínimo fake | M1 | P1 | `0023-0027` | Checksummed import/export |
| `ZGW-0029` | Fault matrix M1 | M1 | P0 | `0028` | Crash points covered |
| `ZGW-0030` | Implementar ChessState/ChessAction ports | M2 | P0 | `0001,0029` | No concrete library leak |
| `ZGW-0031` | Implementar rules adapter | M2 | P0 | `0030` | Legal transitions differential-tested |
| `ZGW-0032` | Implementar FEN/UCI codecs | M2 | P0 | `0031` | Roundtrip and invalid cases |
| `ZGW-0033` | Implementar ASCII renderer | M2 | P1 | `0031` | Orientation metadata deterministic |
| `ZGW-0034` | Implementar image renderer | M2 | P1 | `0031,0023` | Exact-byte artifact reproducibility |
| `ZGW-0035` | Implementar legal/opaque action sets | M2 | P0 | `0031` | Stable ordering and hashes |
| `ZGW-0036` | Implementar state reconstruction task | M2 | P1 | `0032` | Exact and affordance hooks |
| `ZGW-0037` | Implementar move selection task | M2 | P0 | `0032,0035` | Free and grounded modes |
| `ZGW-0038` | Implementar full-game loop | M2 | P0 | `0037` | Formal termination and PGN |
| `ZGW-0039` | Rare-rules/property tests | M2 | P0 | `0038` | Castling/en-passant/promotion/repetition |
| `ZGW-0040` | Ratificar GATE-003 | M3 | P0 | `none` | Artifact retention selected |
| `ZGW-0041` | Implementar content parts | M3 | P0 | `0040,0034` | Text/image/state lowering-ready |
| `ZGW-0042` | Implementar ModelBackend contract | M3 | P0 | `0041` | One-call semantics |
| `ZGW-0043` | Capability negotiation | M3 | P0 | `0042` | Fail/emulate provenance |
| `ZGW-0044` | Pydantic AI Direct adapter | M3 | P0 | `0042,0043` | Golden contract suite |
| `ZGW-0045` | OpenAI-compatible adapter | M3 | P0 | `0042,0043` | Dialect fixtures |
| `ZGW-0046` | Rate limit and timeout policy | M3 | P0 | `0042` | No hidden retry |
| `ZGW-0047` | Implementar R0/R1 | M3 | P0 | `0037,0042` | Trace distinguishes grounding |
| `ZGW-0048` | Implementar R2 repair | M3 | P0 | `0046,0047` | Parse/legal retry only |
| `ZGW-0049` | Implementar KnowledgePacket | M3 | P0 | `0041` | K class/provenance validated |
| `ZGW-0050` | Provider contract matrix | M3 | P0 | `0044-0049` | Offline golden suite |
| `ZGW-0051` | Ratificar GATE-006 e 009 | M4 | P0 | `none` | Engine/cost policy recorded |
| `ZGW-0052` | Implementar UCI supervisor | M4 | P0 | `0051,0038` | Timeout/restart/transcript |
| `ZGW-0053` | Implementar Stockfish evaluator | M4 | P0 | `0052` | Exact provenance and cache key |
| `ZGW-0054` | Implementar R3 structured | M4 | P0 | `0047,0049` | Candidates/claims/decision trace |
| `ZGW-0055` | Implementar metric registry | M4 | P0 | `0053` | Versioned metric definitions |
| `ZGW-0056` | Implementar analytical export | M4 | P0 | `0055` | Parquet schema contract |
| `ZGW-0057` | Implementar DuckDB reports | M4 | P1 | `0056` | Reference queries and slices |
| `ZGW-0058` | Implementar full run bundle | M4 | P0 | `0053-0057` | Import/validate/re-evaluate |
| `ZGW-0059` | Plugin entry points | M5 | P1 | `GATE-007,0058` | First-party discovery |
| `ZGW-0060` | Compatibility/upcaster suite | M5 | P0 | `0058,0059` | Old fixtures remain readable |
| `ZGW-0061` | Security controls verification | M5 | P0 | `0059` | No arbitrary execution paths |
| `ZGW-0062` | Load and quota tests | M5 | P1 | `0058` | Measured operational envelope |
| `ZGW-0063` | Release/SBOM pipeline | M5 | P0 | `GATE-012,0060` | Clean-install RC |
| `ZGW-0064` | Freeze experiment corpus | M6 | P0 | `0063` | Datasets/splits/cards hashed |
| `ZGW-0065` | Execute REP-001 | M6 | P0 | `0064` | Paired report and bundles |
| `ZGW-0066` | Execute GROUND-001 | M6 | P0 | `0064` | Lazy-reasoning hypothesis tested |
| `ZGW-0067` | Execute SKILL-001 | M6 | P0 | `0064` | Correct/wrong/placebo controls |
| `ZGW-0068` | Execute MM-001/MM-002 | M6 | P1 | `0064` | Modality benefit/trust matrix |
| `ZGW-0069` | Execute DEMO-001 | M6 | P1 | `0064` | Token-matched demonstration study |
| `ZGW-0070` | Promote to FULL-001 | M6 | P0 | `0065-0069` | Predeclared promotion rules |
| `ZGW-0071` | Claims and evidence audit | M6 | P0 | `0070` | No claim outruns evidence |
| `ZGW-0072` | Publish v0.1 scientific release | M6 | P0 | `0071` | Allowed bundles, report, citation |

## Regras de execução

- Um issue precisa referenciar requisitos e ADRs relevantes.
- Dependências humanas aparecem como `GATE-*`; não podem ser simuladas por agente.
- Um issue `P0` incompleto impede o exit gate de seu milestone.
- Dividir issue é permitido; manter o ID pai e registrar children.
- Scope creep vira issue novo, não extensão silenciosa do PR atual.
