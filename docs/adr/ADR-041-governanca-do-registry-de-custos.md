---
id: ADR-041
title: "Governança do registry de custos"
status: proposed
decision_owner: "Mestre Mael"
human_gate: GATE-009
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-041: Governança do registry de custos


## Contexto

Preços mudam e modelos têm unidades diferentes. Cost estimates stale podem invalidar comparisons.

## Recomendação

Snapshots manuais versionados com source URL, effective date, currency, units e `stale_after`. Provider-reported invoice data continua separado.

## Opções

1. hardcode;
2. scrape automático;
3. manual registry;
4. user-supplied only.

## Trade-offs

Scraping é frágil. Manual exige manutenção. User-only reduz comparabilidade.

## Reversibilidade

Alta, desde que snapshots antigos permaneçam.
