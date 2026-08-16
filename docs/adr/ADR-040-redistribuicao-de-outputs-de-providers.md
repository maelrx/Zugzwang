---
id: ADR-040
title: "Redistribuição de outputs de providers"
status: proposed
decision_owner: "Mestre Mael"
human_gate: GATE-005
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-040: Redistribuição de outputs de providers


## Contexto

Providers podem impor termos diferentes sobre storage, public sharing e derived datasets.

## Decisão necessária

Definir policy registry por provider e exigir acknowledgement antes de export público.

## Opções

1. responsabilidade exclusiva do usuário;
2. registry advisory;
3. hard blocks por provider;
4. bundles privados por default.

## Trade-offs

Hard blocks ficam stale e podem interpretar termos incorretamente. Advisory melhora segurança sem se tornar parecer jurídico.

## Recomendação

Registry advisory versionado, public export explicitamente confirmado, no legal claims by the software.
