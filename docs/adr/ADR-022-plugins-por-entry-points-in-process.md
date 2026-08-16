---
id: ADR-022
title: "Plugins por entry points, in-process"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-022: Plugins por entry points, in-process


**Status recomendado:** aceitar.  
**Decisão:** PyPA entry points, first-party inicialmente.

### Opções

1. registry hardcoded.
2. import path em config.
3. entry points.
4. subprocess plugins.
5. RPC plugins.

### Trade-offs

Hardcoded impede ecossistema. Import paths são flexíveis e pouco governáveis. Entry points são padrão de packaging. Subprocess resolve trust/dependency conflicts e adiciona IPC, lifecycle e schemas.

### Impactos

- **Direto:** descriptor/API version.
- **Indireto:** plugin third-party é arbitrary code; warning necessário.
- **Exterior:** integrações podem ser distribuídas independentemente.
- **Subjetivo:** extensibilidade real sem construir marketplace prematuro.

### Reversibilidade

Média.

### Reavaliar quando

Plugins não confiáveis ou dependências conflitantes se tornarem comuns.

---
