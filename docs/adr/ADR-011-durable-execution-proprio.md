---
id: ADR-011
title: "Durable execution próprio"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-011: Durable execution próprio


**Status recomendado:** aceitar no v0.1.  
**Decisão:** explicit state machines, checkpoints e resume próprios.

### Opções

1. sem resume.
2. runner próprio.
3. LangGraph.
4. Temporal/DBOS/Prefect.
5. Celery.

### Trade-offs

Sem resume desperdiça API e invalida runs longos. LangGraph traz persistence e agent graphs, mas pode duplicar strategy semantics. Temporal oferece durabilidade real e multi-host, com servidor, workers, determinism constraints e grande superfície. Um runner próprio é trabalho, porém o workflow do v0.1 é finito e precisa de eventos científicos específicos.

### Impactos

- **Direto:** mais código de state machine e fault tests.
- **Indireto:** total controle de attempts, budgets e assistance.
- **Exterior:** instalação sem serviços e bundles compreensíveis.
- **Subjetivo:** evita dependência identitária de um framework; também exige resistir à síndrome “vamos construir nosso próprio Temporal”. O escopo deve permanecer pequeno.

### Reversibilidade

Alta. Migrar runs ativos é difícil; ports podem permitir backend futuro.

### Reavaliar quando

Workers multi-host, human approval longa ou workflows de dias exigirem garantia distribuída.

---
