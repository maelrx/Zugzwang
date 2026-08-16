---
id: ADR-030
title: "Versionamento e compatibilidade"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-030: Versionamento e compatibilidade


**Status recomendado:** aceitar.  
**Decisão:** SemVer packages; schemas e plugin API versionados separadamente.

### Opções

1. versão única para tudo.
2. sem versionamento até 1.0.
3. versões explícitas por contrato.

### Trade-offs

Versão única é simples e não expressa bundle/plugin compatibility. Sem versionamento transforma pre-1.0 em terra arrasada. Contratos separados exigem matriz e migrators.

### Impactos

- **Direto:** `api_version`, event version, metric version.
- **Indireto:** bundles sobrevivem à evolução do código.
- **Exterior:** plugin authors sabem compatibilidade.
- **Subjetivo:** sinaliza respeito por artefatos de pesquisa antigos.

### Reversibilidade

Alta.

### Reavaliar quando

Complexidade de matriz superar ecossistema; simplificar mantendo readers antigos.

---
