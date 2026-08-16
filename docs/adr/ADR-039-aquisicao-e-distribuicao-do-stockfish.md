---
id: ADR-039
title: "Aquisição e distribuição do Stockfish"
status: accepted
decision_owner: "Mestre Mael"
human_gate: GATE-006
date: "2026-08-12"
accepted_date: "2026-08-16"
source: "integrated foundation design"
---

# ADR-039: Aquisição e distribuição do Stockfish


## Contexto

Stockfish é GPLv3. User-provided binary minimiza supply-chain e redistribuição; downloader melhora onboarding.

## Recomendação

v0.1 user-provided path e doctor. Downloader somente em plugin/release separado após política de provenance, checksums e source compliance.

## Opções

1. user-provided;
2. download oficial sob comando;
3. bundle no wheel/container;
4. system package only.

## Trade-offs

Onboarding versus compliance e attack surface.

## Reversibilidade

Média. Binário redistribuído cria obrigações imediatas.
