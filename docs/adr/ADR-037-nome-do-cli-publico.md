---
id: ADR-037
title: "Nome do CLI público"
status: accepted
decision_owner: "Mestre Mael"
human_gate: GATE-004
date: "2026-08-12"
accepted_date: "2026-08-16"
source: "integrated foundation design"
---

# ADR-037: Nome do CLI público

## Decisão ratificada (2026-08-16)

**Mestre Mael escolheu: comando canônico `zugzwang` + alias `zgw`, ambos como entry points de `zugzwang-cli`.**


## Contexto

`zgw` é curto e confortável. `zugzwang` é autoexplicativo e descobrível.

## Recomendação

Distribuição `zugzwang-cli`, comando primário `zugzwang`, alias `zgw` quando packaging permitir sem ambiguidade.

## Opções

1. `zgw`;
2. `zugzwang`;
3. ambos;
4. `zug`.

## Trade-offs

Dois aliases aumentam docs/tests modestamente. Apenas `zgw` cria opacidade. Apenas `zugzwang` é longo em uso repetitivo.

## Reversibilidade

Média, mas scripts públicos tornam renomeação custosa.
