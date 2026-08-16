# Dependency rules

## Allowed graph

```text
core <- runtime <- cli
  ^       ^
  |       |
chess ----+
  ^
plugins depend on core and, only when necessary, runtime/chess
```

## Forbidden dependencies

`core` must not import:

- SQLAlchemy/Alembic;
- Typer/Rich;
- provider SDKs;
- Pydantic AI;
- concrete chess rules library;
- Stockfish/UCI subprocess code;
- filesystem/network modules in domain logic.

`chess` must not import CLI or provider adapters.

`runtime` must not depend on `cli`.

Plugins must not import private runtime internals.

CLI must not execute SQL or manipulate CAS layout directly.

## Boundary types

- domain: frozen/slotted dataclasses and protocols;
- boundary validation: Pydantic strict models;
- persistence rows: adapter-private;
- provider SDK types: adapter-private;
- external JSON: canonical DTOs only.

## Enforcement

- import-linter or custom AST architecture tests;
- public API snapshots;
- package-level contract tests;
- no star imports;
- no re-export of adapter types;
- dependency changes require a PR section explaining why the current package cannot remain independent.
