# Sequência de dependências

## Princípio

A implementação segue de invariantes para efeitos externos. Um adapter nunca define a semântica do domínio que deveria adaptar.

```mermaid
flowchart TD
    D[Human decision gates] --> S[Canonical schemas and IDs]
    S --> C[Core domain contracts]
    C --> R[Runtime application services]
    R --> P[Persistence adapters]
    C --> E[Chess environment]
    R --> B[Provider backends]
    E --> T[Decision strategies]
    B --> T
    T --> V[Evaluators and metrics]
    P --> U[Run bundles and analytics]
    V --> U
    U --> X[Scientific experiments]
```

## Critical path

1. Gate de licença e Python.
2. Identificadores, clocks, money/usage, errors e schema versions.
3. Manifest source → resolved manifest → canonical hash.
4. Domain events e state machines.
5. SQLite/CAS transactional protocol.
6. Fake backend + fake environment vertical slice.
7. Chess environment and renderers.
8. Provider adapters and strategies.
9. Post-hoc evaluators and analytical exports.
10. Run bundle validation and import.
11. Experimental suites.

## Paralelismo seguro

Podem avançar em paralelo depois dos contratos:

- chess renderer e provider fake;
- SQLite repositories e CAS;
- CLI queries e analytical schema;
- experiment cards e knowledge packet authoring;
- contract tests para adapters diferentes.

Não podem avançar de forma independente:

- migrations antes do domain model;
- provider retries antes do attempt model;
- Stockfish metrics antes de metric provenance;
- public plugin API antes de GATE-007;
- package publication antes de GATE-012.
