# Backlog de decisões arquiteturais candidatas

Nem toda pergunta merece ADR antes de existir código. Este backlog impede que questões reais desapareçam, sem congelar escolhas prematuras. Uma candidata vira ADR quando seu trigger ocorre.

| Candidate | Decisão futura | Alternativas | Trigger de promoção |
|---|---|---|---|
| C-001 | Esquema de IDs | UUIDv7, ULID, UUID4 + typed wrappers | M0 domain implementation |
| C-002 | Canonical JSON algorithm | sorted stdlib JSON, RFC 8785/JCS, custom canonicalizer | cross-language verifier demand |
| C-003 | CAS compression | raw, zstd per artifact, pack files | measured disk/throughput data |
| C-004 | Artifact encryption | none, OS/user-managed, envelope encryption plugin | sensitive multi-user/hosted use |
| C-005 | SQLite async access | sync writer thread, aiosqlite, SQLAlchemy async | M1 prototype measurement |
| C-006 | Logging substrate | stdlib JSON, structlog, loguru | M0 observability implementation |
| C-007 | Build backend | Hatchling, setuptools, maturin mixed workspace | GATE-001/002 and Rust decision |
| C-008 | Type checker | Pyright, mypy, both | M0 developer feedback benchmark |
| C-009 | Human CLI rendering | Rich, plain Typer, pluggable renderer | GATE-004 and accessibility requirements |
| C-010 | Secret references | env-only, keyring, file refs, plugin vault | first real provider adapter |
| C-011 | CAS GC policy | manual, age-based, quota-based, pin graph | artifact volume measurement |
| C-012 | Bundle archive container | directory, zip, tar.zst | cross-platform/publication tests |
| C-013 | Provider streaming | no streaming, normalized stream events | use case requiring partial output |
| C-014 | Plugin isolation | in-process, subprocess RPC, WASI/container | first untrusted third-party plugin |
| C-015 | Metric computation engine | Python, DuckDB SQL, mixed registry | M4 performance and portability data |
| C-016 | PGN scope | strict mainline writer, rich parser, external plugin | corpus/import requirements |
| C-017 | Renderer stack | Pillow, SVG-first, Rust renderer | MM pilot determinism/performance |
| C-018 | Price registry distribution | in-repo snapshots, external package, hosted service | volume of provider price changes |
| C-019 | Postgres adapter | SQLAlchemy repository, dedicated implementation | multi-writer/remote trigger |
| C-020 | API transport | FastAPI/OpenAPI, local IPC, gRPC | two real non-CLI consumers |
| C-021 | Run scheduling | in-process queue, daemon, Temporal | multi-host/days-long workload |
| C-022 | Dataset registry | local manifests, DVC/lakeFS, hosted registry | first large external suite |
| C-023 | Contribution attestation | DCO, CLA, none | first external code contribution |
| C-024 | Trademark policy | informal name, trademark guidelines | public ecosystem/hosted product |

## Regra

Agentes podem prototypear alternativas dentro de um Work Order, mas não transformar a candidata em contract público sem ADR. Uma escolha local temporária precisa ser marcada como internal e reversible.
