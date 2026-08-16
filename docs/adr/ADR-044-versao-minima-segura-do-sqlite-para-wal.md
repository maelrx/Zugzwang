---
id: ADR-044
title: "Versão mínima segura do SQLite para WAL"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "integrated foundation design"
---

# ADR-044: Versão mínima segura do SQLite para WAL


## Contexto

A documentação oficial do SQLite registra um WAL-reset bug raro em versões antigas quando múltiplas conexões escrevem/checkpointam concorrentemente. A correção está em 3.51.3+, com backports oficiais 3.44.6 e 3.50.7 e releases 3.53.x atuais.

## Decisão

`zugzwang doctor` verifica `sqlite3.sqlite_version`. WAL multi-connection é recusado em runtime vulnerável, salvo override explícito somente para desenvolvimento. CI inclui uma versão corrigida.

## Alternativas

1. ignorar por raridade;
2. rollback journal;
3. one connection only;
4. enforce fixed SQLite.

## Trade-offs

Enforcement pode exigir Python/runtime mais recente em algumas plataformas. Ignorar é incompatível com o claim de crash consistency.

## Impactos

- dependency/wheel matrix;
- doctor output;
- deployment docs;
- fault tests.

## Reversibilidade

Alta quando versões vulneráveis saírem da matrix.
