---
id: ADR-012
title: "SQLite WAL + single writer"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-012: SQLite WAL + single writer


**Status recomendado:** aceitar.  
**Decisão:** SQLite local, WAL, busy timeout controlado, writer coordenado.

### Opções

1. arquivos JSON somente.
2. SQLite rollback journal.
3. SQLite WAL.
4. Postgres desde o início.
5. DuckDB operacional.

### Trade-offs

Arquivos-only complicam queries, migrations e atomic state. WAL melhora leitura concorrente, mas continua same-host e one-writer. Postgres resolve concorrência distribuída e cria provisioning. DuckDB é excelente para analytics e inadequado como coordinator de jobs mutáveis.

### Impactos

- **Direto:** zero serviço externo e transações confiáveis.
- **Indireto:** workspace não pode ser compartilhado por múltiplos hosts.
- **Exterior:** onboarding de um comando.
- **Subjetivo:** comunica local-first e reduz medo operacional.

### Reversibilidade

Média se repositories isolarem SQL.

### Reavaliar quando

Triggers objetivos da seção 11.10 aparecerem.

---
