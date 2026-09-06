# Architecture Decision Records

Status values: `proposed`, `accepted`, `rejected`, `superseded`.

| ID | Decision | Status | Human gate |
|---|---|---|---|
| [ADR-001](ADR-001-fronteira-do-produto.md) | Fronteira do produto | `accepted` | `none` |
| [ADR-002](ADR-002-monolito-modular-hexagonal.md) | Monólito modular hexagonal | `accepted` | `none` |
| [ADR-003](ADR-003-python-3-13-como-piso-e-rust-restrito.md) | Python 3.13 como piso e Rust restrito | `proposed` | `GATE-002` |
| [ADR-004](ADR-004-licenca-e-biblioteca-de-regras.md) | Licença e biblioteca de regras | `proposed` | `GATE-001` |
| [ADR-005](ADR-005-monorepo-com-uv-workspace.md) | Monorepo com `uv` workspace | `accepted` | `none` |
| [ADR-006](ADR-006-granularidade-de-pacotes.md) | Granularidade de pacotes | `accepted` | `none` |
| [ADR-007](ADR-007-dataclasses-no-dominio-pydantic-nas-bordas.md) | Dataclasses no domínio, Pydantic nas bordas | `accepted` | `none` |
| [ADR-008](ADR-008-yaml-estrito-compilado-para-json-canonico.md) | YAML estrito compilado para JSON canônico | `accepted` | `none` |
| [ADR-009](ADR-009-typer-como-cli-adapter.md) | Typer como CLI adapter | `accepted` | `none` |
| [ADR-010](ADR-010-asyncio-com-concorrencia-estruturada.md) | `asyncio` com concorrência estruturada | `accepted` | `none` |
| [ADR-011](ADR-011-durable-execution-proprio.md) | Durable execution próprio | `accepted` | `none` |
| [ADR-012](ADR-012-sqlite-wal-single-writer.md) | SQLite WAL + single writer | `accepted` | `none` |
| [ADR-013](ADR-013-sqlalchemy-core-alembic.md) | SQLAlchemy Core + Alembic | `accepted` | `none` |
| [ADR-014](ADR-014-cas-eventos-projections.md) | CAS + eventos + projections | `accepted` | `none` |
| [ADR-015](ADR-015-parquet-duckdb.md) | Parquet + DuckDB | `accepted` | `none` |
| [ADR-016](ADR-016-contrato-proprio-de-provider.md) | Contrato próprio de provider | `accepted` | `none` |
| [ADR-017](ADR-017-pydantic-ai-direct-como-adapter-nao-kernel.md) | Pydantic AI Direct como adapter, não kernel | `accepted` | `none` |
| [ADR-018](ADR-018-adapter-openai-compatible-direto.md) | Adapter OpenAI-compatible direto | `accepted` | `none` |
| [ADR-019](ADR-019-retry-fallback-e-routing-explicitos.md) | Retry, fallback e routing explícitos | `accepted` | `none` |
| [ADR-020](ADR-020-estrategias-explicitas-em-vez-de-generic-graph-runtime.md) | Estratégias explícitas em vez de generic graph runtime | `accepted` | `none` |
| [ADR-021](ADR-021-tool-protocol-proprio-mcp-na-borda.md) | Tool protocol próprio; MCP na borda | `accepted` | `none` |
| [ADR-022](ADR-022-plugins-por-entry-points-in-process.md) | Plugins por entry points, in-process | `accepted` | `none` |
| [ADR-023](ADR-023-estado-completo-e-uci-canonico.md) | Estado completo e UCI canônico | `accepted` | `none` |
| [ADR-024](ADR-024-engine-uci-externa-e-pos-hoc.md) | Engine UCI externa e pós-hoc | `accepted` | `none` |
| [ADR-025](ADR-025-metricas-versionadas-com-provenance.md) | Métricas versionadas com provenance | `accepted` | `none` |
| [ADR-026](ADR-026-cache-seletivo.md) | Cache seletivo | `accepted` | `none` |
| [ADR-027](ADR-027-eventos-proprios-logs-json-e-otel-opcional.md) | Eventos próprios, logs JSON e OTel opcional | `accepted` | `none` |
| [ADR-028](ADR-028-seguranca-por-ausencia-de-execucao-arbitraria.md) | Segurança por ausência de execução arbitrária | `accepted` | `none` |
| [ADR-029](ADR-029-api-futura-como-adapter.md) | API futura como adapter | `accepted` | `none` |
| [ADR-030](ADR-030-versionamento-e-compatibilidade.md) | Versionamento e compatibilidade | `accepted` | `none` |
| [ADR-031](ADR-031-testes-contract-property-fault-first.md) | Testes contract/property/fault first | `accepted` | `none` |
| [ADR-032](ADR-032-release-e-supply-chain.md) | Release e supply chain | `accepted` | `none` |
| [ADR-033](ADR-033-content-parts-multimodais-tipados.md) | Content parts multimodais tipados | `accepted` | `none` |
| [ADR-034](ADR-034-eixos-de-assistencia-h-e-k-independentes.md) | Eixos de assistência H e K independentes | `accepted` | `none` |
| [ADR-035](ADR-035-knowledgepacket-estatico-antes-de-rag.md) | KnowledgePacket estático antes de RAG | `accepted` | `none` |
| [ADR-036](ADR-036-politica-padrao-de-retencao-de-evidencia.md) | Política padrão de retenção de evidência | `proposed` | `GATE-003` |
| [ADR-037](ADR-037-nome-do-cli-publico.md) | Nome do CLI público | `proposed` | `GATE-004` |
| [ADR-038](ADR-038-idioma-canonico-da-documentacao.md) | Idioma canônico da documentação | `proposed` | `GATE-010` |
| [ADR-039](ADR-039-aquisicao-e-distribuicao-do-stockfish.md) | Aquisição e distribuição do Stockfish | `proposed` | `GATE-006` |
| [ADR-040](ADR-040-redistribuicao-de-outputs-de-providers.md) | Redistribuição de outputs de providers | `proposed` | `GATE-005` |
| [ADR-041](ADR-041-governanca-do-registry-de-custos.md) | Governança do registry de custos | `proposed` | `GATE-009` |
| [ADR-042](ADR-042-standard-chess-no-primeiro-release.md) | Standard chess no primeiro release | `proposed` | `GATE-008` |
| [ADR-043](ADR-043-estabilidade-da-api-de-plugins.md) | Estabilidade da API de plugins | `proposed` | `GATE-007` |
| [ADR-044](ADR-044-versao-minima-segura-do-sqlite-para-wal.md) | Versão mínima segura do SQLite para WAL | `accepted` | `none` |

| [ADR-045](ADR-045-topologia-de-publicacao-dos-packages.md) | Topologia de publicação dos packages | `proposed` | `GATE-012` |
| [ADR-059](ADR-059-multi-agent-review.md) | R5 multi-agent review por lance | `accepted` | `none` |
| [ADR-060](ADR-060-turn-scoped-legality-and-memory-ablation.md) | Legal tree e ablação de memória por episódio | `proposed` | `none` |

## Normative rule

An accepted ADR overrides the master design when they conflict. Proposed human-gated ADRs cannot be silently accepted by an agent.

## Workflow

1. Copy `ADR-TEMPLATE.md`.
2. Fill context, alternatives, trade-offs, impacts, reversibility and evidence.
3. Link affected requirements and protocols.
4. Human-owned gates require an explicit operator decision.
5. Update this index and `docs/decisions/DECISIONS.yaml`.
