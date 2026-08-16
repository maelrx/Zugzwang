---
id: ADR-043
title: "Estabilidade da API de plugins"
status: proposed
decision_owner: "Mestre Mael"
human_gate: GATE-007
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-043: Estabilidade da API de plugins


## Contexto

Publicar plugins cedo incentiva adoção e congela contracts antes de evidência.

## Recomendação

First-party entry points em v0.1; third-party API marcada experimental até 0.3; compatibility fixtures desde M0.

## Opções

1. no plugins before 1.0;
2. experimental;
3. stable from v0.1.

## Trade-offs

Experimental equilibra feedback e liberdade. Precisa de mensagens claras e version ranges.

## Reversibilidade

Baixa depois que terceiros publicarem packages.
