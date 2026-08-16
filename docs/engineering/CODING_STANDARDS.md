# Padrões de código

## Python

- typing estrito em APIs e domain boundaries;
- `from __future__ import annotations` enquanto necessário;
- dataclasses frozen/slots no domínio quando apropriado;
- Pydantic strict em entrada/saída e persisted protocol models;
- `pathlib.Path`, UTC aware timestamps e injected clocks;
- `Decimal` para valores monetários; usage desconhecido não vira zero;
- IDs tipados, não strings intercambiáveis;
- enums e discriminated unions em protocolos persistidos;
- nenhuma exception genérica atravessa boundary sem machine code e cause.

## Async

- I/O externo assíncrono; CPU/blocking via boundary explícita;
- structured concurrency e cancellation propagation;
- sem tasks órfãs criadas por `create_task` sem owner;
- timeout por operação, não um timeout global indistinto;
- semaphore/rate limiter scoped por backend/modelo;
- não segurar transação SQLite durante chamada de provider/engine.

## Pure core

`zugzwang-core` não importa:

- Typer/FastAPI;
- SQLAlchemy/Alembic;
- provider SDKs;
- Pydantic AI;
- Stockfish/process supervisor;
- concrete chess library;
- filesystem/network implementations.

## Serialization

- canonical JSON: UTF-8, normalized keys, explicit schema version;
- persisted enums nunca dependem de `repr` Python;
- unknown fields obey version policy, not accidental permissiveness;
- large bytes live in CAS and are referenced by hash;
- user-facing YAML is source, resolved JSON is execution truth.

## Errors

Um erro precisa responder:

```text
what failed?
where?
which retryability class?
was external work possibly accepted?
which evidence artifact supports the diagnosis?
```

Nunca capturar `Exception` e continuar silenciosamente.

## Comments and docs

Comentários explicam invariants, causal constraints e por que uma alternativa foi rejeitada. Não narram sintaxe. Public contracts recebem docstrings e examples. TODO precisa de issue ID.

## Tests as contracts

- fixtures pequenas e legíveis;
- property tests para state/action/serialization;
- golden fixtures para provider dialects;
- fault tests para every write/call boundary;
- no real network in default test suite;
- randomness always seeded and recorded.
