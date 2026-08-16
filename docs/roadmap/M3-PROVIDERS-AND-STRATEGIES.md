# M3: Providers e estratégias R0-R2

## Objetivo

Executar modelos reais sem permitir que SDKs definam retries, tools, memory ou agency.

## Entry gates

- GATE-003 ratificado para artifacts reais.
- M2 concluído.

## Entregáveis

- canonical ModelRequest/ModelResponse/Usage/CapabilityReport;
- typed content parts;
- deterministic fake backend;
- Pydantic AI Direct adapter;
- direct OpenAI-compatible adapter;
- capability negotiation and native/emulated provenance;
- rate limits, timeout taxonomy and attempt ledger;
- R0 direct, R1 grounded, R2 legality repair;
- KnowledgePacket injection K0-K6 sem retrieval dinâmico;
- provider golden fixtures and normalization tests.

## Exit gate

O mesmo test vector passa por fake e adapters, preserva raw/lowered forms, detecta unsupported capabilities antes da cobrança e não realiza retry invisível.
