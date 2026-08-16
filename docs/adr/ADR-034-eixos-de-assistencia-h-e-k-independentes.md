---
id: ADR-034
title: "Eixos de assistência H e K independentes"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-034: Eixos de assistência H e K independentes


## Contexto

A taxonomia H0-H7 mede assistência operacional e estratégica. Ela não distingue persona, princípios genéricos, knowledge packets e current-position analysis.

## Decisão

Persistir dois eixos: `H` para formal/strategic assistance e `K` para external knowledge. Declared e effective classes são calculadas separadamente.

## Alternativas

1. uma escala única;
2. tags livres;
3. H/K independentes;
4. grafo completo sem classes.

## Trade-offs

Uma escala única ordena coisas incomparáveis. Tags não permitem enforcement. H/K simplifica sem apagar o event graph.

## Impactos

- manifests e reports sempre exibem H/K;
- tools e knowledge artifacts carregam impact;
- protocol fingerprint muda;
- leaderboards não agregam classes incompatíveis.

## Emenda

ADR-047 (2026-08-16) substitui a semântica das classes K do kernel pela
taxonomia oficial K0-K7 documentada em PROTOCOL_TAXONOMY.md §3. A decisão
original (eixos H e K independentes, declared vs effective) permanece.

## Reversibilidade

Baixa após publicação de bundles, portanto entra antes do scaffold.
