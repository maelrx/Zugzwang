---
id: ADR-028
title: "Segurança por ausência de execução arbitrária"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-028: Segurança por ausência de execução arbitrária


**Status recomendado:** aceitar.  
**Decisão:** model output é dados; no shell/code/fs/network tools por padrão.

### Opções

1. agent sandbox completo desde o início.
2. execução local aberta.
3. tool surface mínima.

### Trade-offs

Sandbox completo é outro produto e difícil de fazer corretamente. Execução aberta reproduz specification gaming e risco local. Surface mínima é suficiente para xadrez e reduz threat model.

### Impactos

- **Direto:** allowlists, schemas e process hardening.
- **Indireto:** limita experiências general-agent no v0.1.
- **Exterior:** adoção local mais segura.
- **Subjetivo:** projeto parece menos “mágico”, mais confiável.

### Reversibilidade

Alta em segurança: uma vez que ecossistema depende de shell livre, restringir quebra workflows.

### Reavaliar quando

Code-agent research virar vertical explícita com sandbox dedicado.

---
