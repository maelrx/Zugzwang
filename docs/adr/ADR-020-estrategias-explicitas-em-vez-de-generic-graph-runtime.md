---
id: ADR-020
title: "Estratégias explícitas em vez de generic graph runtime"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-020: Estratégias explícitas em vez de generic graph runtime


**Status recomendado:** aceitar.  
**Decisão:** classes/state machines versionadas para R0–R3.

### Opções

1. funções simples por experimento.
2. graph DSL interno.
3. LangGraph/Pydantic Graph.
4. strategy interface + código Python explícito.

### Trade-offs

Funções isoladas fragmentam artifacts. Graph DSL visualiza workflows e adiciona linguagem, serialização e runtime. Strategy interface permite código legível e traces padronizados. Quando search/debate surgirem, podem usar um graph interno no plugin sem definir o core inteiro.

### Impactos

- **Direto:** cada strategy possui schema e trace.
- **Indireto:** experimentos comparam orquestração separadamente do model.
- **Exterior:** pesquisadores podem implementar novas strategies em Python normal.
- **Subjetivo:** evita canvas de nós para representar um `for` de três passos.

### Reversibilidade

Alta se strategy API for mal desenhada.

### Reavaliar quando

Múltiplas strategies repetirem primitivas de graph complexas e comprovadas.

---
