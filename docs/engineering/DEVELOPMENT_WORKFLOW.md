# Workflow de desenvolvimento

## 1. Do backlog ao merge

```text
Decision gate → Issue/Work Order → Skill → Branch/worktree → Tests → Review → Merge → Traceability
```

### Branches

- `main`: sempre instalável e com migrations válidas;
- `feat/ZGW-XXXX-slug`;
- `fix/ZGW-XXXX-slug`;
- `research/EXP-ID-slug` para tooling experimental, nunca para editar outcomes.

Preferir worktree isolado para cada agente concorrente. Nenhum agente compartilha working tree mutável com outro.

## 2. Antes de codar

- confirmar gate state em `docs/decisions/DECISIONS.yaml`;
- ler issue, requirements, ADRs e nested `AGENTS.md`;
- executar foundation validator;
- inspecionar testes existentes;
- registrar plano de delta e risco.

## 3. Commits

Cada commit deve preservar um estado coerente e usar assunto:

```text
feat(runtime): implement committed-step resume [ZGW-0027]
fix(provider): classify ambiguous timeout [ZGW-0046]
docs(adr): ratify rules substrate [GATE-001]
```

Não misturar refactor amplo, behavior change, schema migration e docs cosméticas no mesmo commit.

## 4. Pull requests

PR precisa incluir:

- problema e non-goals;
- requirements/ADRs/gates;
- alteração de behavior e data model;
- commands de teste e resultados;
- migrations/compatibility;
- security/privacy/provenance impact;
- screenshots somente quando interface existir;
- follow-ups explicitamente fora do escopo.

## 5. Definition of done

- implementation atende acceptance criteria;
- tests relevantes passam offline;
- error paths e cancellation testados;
- schemas/docs/examples atualizados;
- nenhum raw secret/response entra no Git;
- architecture boundaries permanecem verdes;
- changelog recebe mudança pública;
- reviewer independente confirma invariantes;
- work order recebe handoff packet.

## 6. Research code

Código exploratório pode existir em `research/` ou notebooks futuros, mas:

- não define canonical metrics;
- não escreve diretamente no operational DB;
- consome bundles/exported Parquet;
- possui seed, environment and dependency capture;
- resultados promovidos ao produto exigem ADR/requirement normal.
