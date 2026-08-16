# Technology radar

O radar distingue decisão aceita de ferramenta apenas estudada. “Adopt” significa apropriada para o caminho crítico após os gates, não dependência já instalada.

| Ring | Technology/approach | Uso proposto | Racional e limite |
|---|---|---|---|
| Adopt | Python | kernel/application/adapters | ecossistema ML e produtividade; versão depende de GATE-002 |
| Adopt | uv workspace | monorepo e lock | packages/plugins com lock compartilhado |
| Adopt | modular monolith/hexagonal | topology | baixa operação, boundaries fortes |
| Adopt | Pydantic strict + JSON Schema | bordas e protocolos | validação/tooling; domínio continua independente |
| Adopt | asyncio | external I/O | concorrência bounded, não distributed runtime |
| Adopt | SQLite WAL + single writer | operational plane | local-first; doctor exige versão segura |
| Adopt | filesystem CAS | evidence blobs | integridade, dedup e portabilidade |
| Adopt | Parquet + DuckDB | analytics | scans locais e bundles independentes |
| Adopt | UCI | engine boundary | processo externo e provenance explícita |
| Trial | Pydantic AI Direct | provider adapter | transporte/schema apenas, nunca Agent semantics |
| Trial | direct OpenAI-compatible adapter | local/provider dialects | compatibilidade é explicitamente parcial |
| Trial | Rust/PyO3 rules island | permissive chess substrate | depende de GATE-001 e wheel plan |
| Trial | OpenTelemetry | optional export | eventos próprios permanecem suficientes |
| Assess | LiteLLM bridge | long-tail providers | routing/retries podem ocultar protocolo |
| Assess | MCP adapter | external tools | somente na borda, trust/assistance declarados |
| Assess | FastAPI | future API adapter | somente após contract demand pós-M6 |
| Assess | Postgres/S3 | future remote plane | trigger por multi-host/concurrency real |
| Hold | Temporal/LangGraph as kernel | durable execution | duplicaria state/retry semantics no v0.1 |
| Hold | Vector database/RAG | knowledge augmentation | static KnowledgePacket antes de retrieval |
| Hold | Ray/Kafka/Kubernetes | distribution | nenhuma necessidade medida |
| Hold | Web UI | product interface | API/query contracts primeiro |
| Reject v0.1 | arbitrary code tools | agent capability | security/specification-gaming surface |
| Reject v0.1 | single Elo leaderboard | reporting | mistura capacidades e protocolos |
