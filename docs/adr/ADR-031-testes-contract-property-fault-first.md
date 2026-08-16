---
id: ADR-031
title: "Testes contract/property/fault first"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-031: Testes contract/property/fault first


**Status recomendado:** aceitar.  
**Decisão:** CI offline; providers reais opt-in.

### Opções

1. unit tests tradicionais.
2. snapshots/e2e predominantes.
3. pirâmide especializada.

### Trade-offs

Unit tests não capturam adapters/crashes. E2E real é caro, flaky e mutável. Contract/property/fault tests cobrem o que torna kernel confiável.

### Impactos

- **Direto:** fake provider, fake engine, crash injector e architecture tests.
- **Indireto:** refactors seguros e plugins verificáveis.
- **Exterior:** contribuidores rodam CI sem chaves.
- **Subjetivo:** qualidade deixa de depender de “joguei uma partida e pareceu funcionar”.

### Reversibilidade

Média.

### Reavaliar quando

Coverage não refletir bugs reais; ajustar suite por incidentes.

---
