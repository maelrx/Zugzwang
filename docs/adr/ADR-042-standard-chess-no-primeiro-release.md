---
id: ADR-042
title: "Standard chess no primeiro release"
status: proposed
decision_owner: "Mestre Mael"
human_gate: GATE-008
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-042: Standard chess no primeiro release


## Contexto

Chess960 é cientificamente valioso para OOD, mas amplia rules, notation, castling, suites e conformance.

## Recomendação

Standard chess como supported happy path. Chess960 aparece como experimental capability somente se o substrate já o entrega sem atrasar M2.

## Opções

1. standard only;
2. standard + Chess960 experimental;
3. variants generic from start.

## Trade-offs

Variants melhoram generalização do design e aumentam surface de bugs formais.

## Reversibilidade

Alta se state/action contracts não assumirem initial setup fixo.
