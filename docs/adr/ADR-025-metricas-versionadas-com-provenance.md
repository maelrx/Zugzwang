---
id: ADR-025
title: "Métricas versionadas com provenance"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-025: Métricas versionadas com provenance


**Status recomendado:** aceitar.  
**Decisão:** `MetricDefinition` + `MetricObservation`; sem colunas ad hoc como contrato.

### Opções

1. dict de métricas.
2. tabelas fixas.
3. registry versionado.

### Trade-offs

Dict é flexível e semanticamente frágil. Tabelas fixas são eficientes e fechadas. Registry permite extensão, ao custo de validação e joins.

### Impactos

- **Direto:** IDs, versões e evaluator metadata.
- **Indireto:** reavaliações coexistem sem sobrescrever.
- **Exterior:** pesquisadores sabem o que um número significa.
- **Subjetivo:** reduz marketing estatístico por ambiguidade.

### Reversibilidade

Alta. Métricas sem provenance não podem ser corrigidas retroativamente.

### Reavaliar quando

Query performance exigir projections especializadas, mantendo registry como semântica.

---
