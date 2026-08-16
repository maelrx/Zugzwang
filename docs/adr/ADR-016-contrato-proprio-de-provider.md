---
id: ADR-016
title: "Contrato próprio de provider"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-016: Contrato próprio de provider


**Status recomendado:** aceitar.  
**Decisão:** `ModelBackend` e canonical request/response pertencem ao Zugzwang.

### Opções

1. usar tipos de um SDK/provider.
2. usar tipos de LiteLLM/Pydantic AI como domínio.
3. possuir contrato próprio e adapters.

### Trade-offs

Tipos externos reduzem mapping e criam lock-in semântico. Contrato próprio exige acompanhar evolução e evitar lowest-common-denominator. Capability negotiation + extensions preservam features sem contaminar o core.

### Impactos

- **Direto:** mapping e contract tests.
- **Indireto:** trocar integração não altera manifests/bundles.
- **Exterior:** plugin ecosystem tem API estável.
- **Subjetivo:** projeto controla seu método científico; não fica “skin” de um framework.

### Reversibilidade

Muito alta. Esse contrato aparece em todo artefato.

### Reavaliar quando

O contrato comum bloquear features essenciais ou ficar maior que os adapters.

---
