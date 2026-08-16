# Fronteira OSS e produto hosted futuro

## Princípio

O kernel necessário para confiar num resultado deve permanecer aberto. Serviços futuros podem vender conveniência, escala e operação, nunca a capacidade exclusiva de verificar o experimento.

## Camada open source

- core contracts;
- local runtime;
- CLI;
- SQLite/CAS/Parquet implementation;
- manifest, event and bundle schemas;
- chess environment;
- provider and evaluator plugin interfaces;
- experiment suites;
- offline reports;
- import/export;
- assistance classification;
- reproducibility validators.

## Possível camada hosted futura

- managed workers and queues;
- team tenancy and access control;
- encrypted secret vault;
- centralized artifact storage;
- scheduled reruns against new model snapshots;
- provider quota coordination;
- collaborative experiment registry;
- public/private benchmark dashboards;
- large-scale statistical execution;
- hosted immutable bundle publication;
- compliance and audit exports.

## Guardrail contra open-core hostil

Um usuário local deve conseguir:

- executar;
- exportar;
- importar;
- analisar;
- verificar;
- criar plugins;
- publicar bundles;

sem uma conta hosted.

## Sequência de validação

1. kernel usado por nós;
2. uma reprodução externa;
3. plugin externo;
4. suite externa;
5. apenas então debate de hosted control plane.

O produto hosted não deve ditar Postgres, S3 ou autenticação no design do v0.1. Ports e DTOs bastam.
