# Matriz de alternativas arquiteturais

Este mapa não substitui ADRs. Ele mostra rapidamente onde cada escolha vive e quais consequências externas carrega.

| Componente | Recomendação | Alternativas principais | Impacto dominante | ADR/Gate |
|---|---|---|---|---|
| Product boundary | chess-first research kernel | universal agents, chess bot, arena | foco científico e adoção | ADR-001 |
| Topology | modular monolith | microservices, single script | operabilidade vs boundaries | ADR-002 |
| Language | Python + Rust restrito | pure Python, Rust-first | contributor UX, wheels, performance | ADR-003/GATE-002 |
| Rules | permissive substrate proposed | python-chess GPL, split plugin | license/ecosystem/correctness speed | ADR-004/GATE-001 |
| Workspace | uv monorepo | Poetry, PDM, multi-repo | lock consistency and plugin development | ADR-005 |
| Packages | four core physical packages | one package, micro-packages | release choreography | ADR-006, ADR-045/GATE-012 |
| Domain models | dataclasses + Pydantic edges | Pydantic everywhere, attrs | purity vs convenience | ADR-007 |
| Config | strict YAML → canonical JSON | Hydra, Python config, CUE/Jsonnet | reproducibility vs expressiveness | ADR-008 |
| CLI | Typer | argparse, Click | ergonomics vs dependency | ADR-009/GATE-004 |
| Concurrency | asyncio | sync/thread, trio, distributed | ecosystem and cancellation | ADR-010 |
| Durable execution | custom bounded runner | Temporal, LangGraph | semantic control vs framework power | ADR-011 |
| Operational DB | SQLite WAL | Postgres, embedded KV | local-first vs multi-host | ADR-012 |
| DB layer | SQLAlchemy Core/Alembic | ORM, raw SQL | migrations/typing vs simplicity | ADR-013 |
| Evidence | CAS + events + projections | blobs in SQL, pure event sourcing | auditability vs complexity | ADR-014 |
| Analytics | Parquet/DuckDB | SQL operational DB, pandas files | portability and scan speed | ADR-015 |
| Provider contract | owned narrow port | LiteLLM/Pydantic types public | independence vs integration speed | ADR-016 |
| Provider substrate | Pydantic AI Direct | LiteLLM, direct SDK per provider | coverage vs semantic leakage | ADR-017 |
| Local inference | direct compatible adapter | one generic gateway | dialect visibility | ADR-018 |
| Retry/routing | runtime explicit | SDK/framework automatic | attribution and cost | ADR-019 |
| Strategy runtime | explicit strategies | generic graph framework | inspectability vs flexibility | ADR-020 |
| Tools | typed internal protocol | MCP internal, arbitrary functions | trust and assistance tracking | ADR-021 |
| Plugins | entry points, in-process | registry/import scanning/subprocess | simplicity vs isolation | ADR-022/GATE-007 |
| Chess action | UCI canonical | SAN, custom tokens | ambiguity vs familiarity/leakage | ADR-023 |
| Engine | external UCI, post-hoc | bundled/embedded/live | license and capability attribution | ADR-024/GATE-006 |
| Metrics | versioned observations | mutable aggregate names | comparability and storage | ADR-025 |
| Cache | deterministic selective | cache all, no cache | cost vs stochastic integrity | ADR-026 |
| Observability | domain events + JSON logs | OTel-only, SaaS | local sufficiency vs integration | ADR-027 |
| Security | no arbitrary execution | shell/code tools | capability vs attack surface | ADR-028 |
| API/UI | future adapters | server-first | focus vs early product polish | ADR-029 |
| Compatibility | independent schema versions | package version only | evidence longevity | ADR-030 |
| Testing | contract/property/fault-first | unit/e2e-heavy | corruption resistance | ADR-031 |
| Supply chain | locked/SBOM/signed path | informal releases | trust and contributor burden | ADR-032 |
| Multimodal | typed content parts/CAS | SDK-native types, strings | exact evidence vs mapping work | ADR-033 |
| Assistance | independent H/K axes | one scalar, prose only | causal attribution | ADR-034 |
| Knowledge | static packets first | RAG/vector DB now | controlled causality vs flexibility | ADR-035 |
