---
id: ADR-029
title: "API futura como adapter"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-029: API futura como adapter


**Status recomendado:** aceitar.  
**Decisão:** preparar contracts, não implementar servidor.

### Opções

1. construir FastAPI agora.
2. CLI-only sem seams.
3. application services + API futura.

### Trade-offs

FastAPI cedo adiciona deployment e auth questions. CLI acoplada impede evolução. Service layer entrega seam por baixo custo.

### Impactos

- **Direto:** commands/queries tipados.
- **Indireto:** mesma semântica em CLI e Web.
- **Exterior:** frontend futuro ganha OpenAPI/JSON Schema.
- **Subjetivo:** evita UI-driven architecture antes de existir workload.

### Reversibilidade

Baixa.

### Reavaliar quando

Usuários precisarem acompanhar runs remotamente ou múltiplos clientes concorrentes.

---
