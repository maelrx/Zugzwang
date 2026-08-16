# M5: Robustez da plataforma

## Objetivo

Preparar o kernel para colaboração OSS, plugins first-party e release pre-1.0 responsável.

## Entregáveis

- entry-point plugin discovery;
- plugin compatibility matrix;
- trust metadata e explicit enablement;
- migration/upcaster tests;
- architecture and API surface checks;
- load tests de SQLite/CAS e artifact quotas;
- threat-model verification;
- signed release process, SBOM, provenance and dependency review;
- docs lints, examples smoke tests and reproducibility report;
- public API inventory.

## Entry gates

GATE-007 e GATE-012.

## Exit gate

Release candidate instala em ambiente limpo, executa fake demo, exporta SBOM, passa fault/replay tests e não contém decisões humanas pendentes que afetem o artefato distribuído.
