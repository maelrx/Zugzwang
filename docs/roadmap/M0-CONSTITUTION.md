# M0: Constituição do kernel

## Objetivo

Converter a fundação documental em um workspace executável mínimo sem antecipar decisões humanas nem implementar xadrez real.

## Entry gates

- GATE-001, GATE-002 e GATE-004 ratificados.
- ADR-001..008 revisadas após as decisões.

## Entregáveis

- workspace `uv` e packages físicos;
- configuração Ruff, Pyright/mypy, pytest e coverage;
- IDs, clocks, decimal money/usage, schema versions e errors;
- Pydantic models de borda e dataclasses imutáveis de domínio;
- source/resolved manifest e canonical hashing;
- fake provider, fake environment e fake evaluator;
- CLI `init`, `doctor`, `validate`, `plan` em modo fake;
- architecture tests e contract test harness;
- CI offline, lockfile e SBOM exportável.

## Vertical slice de saída

Um manifesto fake é validado, resolvido, planejado e executado por um episódio de um step, produzindo eventos e um artifact pequeno. Nenhuma rede, banco persistente ou engine real é necessária.

## Exit gate

- todos os schemas regeneráveis e estáveis;
- nenhum import proibido;
- `python scripts/validate_foundation.py --strict` verde;
- determinismo do canonical hash comprovado em property tests;
- decisão record atualizada.

## Não fazer

SQLite completo, Stockfish, providers reais, Web API, RAG, UI ou partidas completas.
