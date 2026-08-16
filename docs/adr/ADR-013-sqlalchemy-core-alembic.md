---
id: ADR-013
title: "SQLAlchemy Core + Alembic"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-013: SQLAlchemy Core + Alembic


**Status recomendado:** aceitar.  
**Decisão:** SQLAlchemy Core, sem ORM stateful; Alembic.

### Opções

1. sqlite3 e SQL manual.
2. SQLAlchemy Core.
3. SQLAlchemy ORM.
4. SQLModel.
5. lightweight query builder.

### Trade-offs

SQL manual maximiza transparência e duplica dialect/migration work. ORM acelera CRUD e adiciona session identity/lazy behavior que não ajuda evented runtime. Core fornece transações, tipos e caminho Postgres sem esconder SQL por completo.

### Impactos

- **Direto:** repositories explícitos e migrations testáveis.
- **Indireto:** menos acoplamento a SQLite.
- **Exterior:** contributors encontram stack familiar.
- **Subjetivo:** equilíbrio entre “SQL é real” e “não precisamos concatenar strings até 2030”.

### Reversibilidade

Média.

### Reavaliar quando

SQLAlchemy overhead ou complexity superar benefícios medidos.

---
