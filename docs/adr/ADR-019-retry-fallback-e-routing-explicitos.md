---
id: ADR-019
title: "Retry, fallback e routing explícitos"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-019: Retry, fallback e routing explícitos


**Status recomendado:** aceitar.  
**Decisão:** runtime central é autoridade; fallback off.

### Opções

1. aceitar defaults dos SDKs.
2. retry central.
3. proxy gerencia tudo.

### Trade-offs

Defaults são convenientes e contaminam calls/custo. Centralização exige desativar ou detectar retries internos. Fallback melhora uptime e muda o objeto medido.

### Impactos

- **Direto:** attempt model e retry taxonomy.
- **Indireto:** custos e pass@k ficam honestos.
- **Exterior:** resultados comparáveis e auditáveis.
- **Subjetivo:** menos “funciona magicamente”, mais confiança.

### Reversibilidade

Alta, porque logs antigos sem attempts não podem ser recuperados.

### Reavaliar quando

Provider não permitir controle suficiente; nesse caso a limitação vira metadata, não licença para omissão.

---
