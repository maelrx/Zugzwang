---
id: ADR-026
title: "Cache seletivo"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-026: Cache seletivo


**Status recomendado:** aceitar.  
**Decisão:** CAS dedup e engine cache on; model response cache off em runs científicos.

### Opções

1. sem cache.
2. tudo cacheado.
3. cache por camada.
4. semantic cache.

### Trade-offs

Model cache altera sampling e pode reutilizar respostas de snapshots mutáveis. Engine evaluation é cara e determinística o suficiente sob key rigorosa. Semantic cache é metodologicamente tóxico para benchmark.

### Impactos

- **Direto:** cache keys e hit events.
- **Indireto:** desenvolvimento barato sem falsificar runs.
- **Exterior:** bundles declaram cache hits.
- **Subjetivo:** evita que “economia” vire variável oculta.

### Reversibilidade

Média.

### Reavaliar quando

Provider oferecer cache explícito cobrado, que deve ser modelado como capability/custo, não cache local invisível.

---
