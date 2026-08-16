# M1: Execução local mínima

## Objetivo

Provar durable local execution com semântica explícita de attempt, commit, interruption e resume.

## Entregáveis

- Run/Episode/Step state machines;
- persistence writer single-thread logical;
- SQLite WAL repositories e migrations;
- CAS atômico com SHA-256;
- append-only events + operational projections na mesma transação;
- budget ledger;
- structured cancellation;
- `run`, `status`, `inspect`, `cancel`, `resume`;
- export/import de bundle mínimo fake;
- fault injection em cada boundary.

## Invariantes

- ação commitada nunca é reaplicada;
- raw attempt nunca é sobrescrito;
- projection e event avançam atomicamente;
- artifact ref nunca aponta para bytes ausentes;
- finalização é idempotente;
- timeout ambíguo não vira retry silencioso.

## Exit gate

Crash tests interrompem o runtime antes/depois de cada write relevante e o run sempre termina em estado diagnosticável, retomável ou explicitamente falho.
