# ZGW-0087 — Reconciliação do baseline (CB-WO-01 do PRD CognitiveBoard v0.1)

Data: 2026-09-06 · Ordem: [ZGW-0087](../work-orders/ZGW-0087.md) · Fonte do escopo:
PRD `Zugzwang_PRD_CognitiveBoard_v0.1.md` §38.2, §3.5, §25.1, §40.5, §48.1–48.3,
ADR-CB-020, RISK-13, TEST-081.

## 1. Comparação head × referência (PRD §46.4/§48.1)

O PRD registra o baseline consultado como `1317ad55761ec590170c7b48d6e3b0893eb49160`
[^R01] — **idêntico ao head atual da `main`**. Não há drift estrutural a reconciliar;
as divergências abaixo são entre intenção (PRD/ADRs) e implementação, não entre commits.
Blob SHA-1 dos pontos de integração que o PRD manda reavaliar a cada atualização
(ambiente, gateway, workspace, memory, strategies, coordinator, contracts, migrations):

| Ponto de integração | Caminho | Blob (head) |
|---|---|---|
| Ambiente | `packages/zugzwang-chess/src/zugzwang_chess/environment/standard.py` | `0cf64d3d52db` |
| Gateway de legalidade | `packages/zugzwang-runtime/src/zugzwang_runtime/execution/legality.py` | `c09c0a062231` |
| Workspace de busca | `packages/zugzwang-runtime/src/zugzwang_runtime/search/workspace.py` | `7a2ee9e9a228` |
| Memória de busca | `packages/zugzwang-runtime/src/zugzwang_runtime/search/memory.py` | `4d6474367b1e` |
| Coordinator durable | `packages/zugzwang-runtime/src/zugzwang_runtime/execution/durable_coordinator.py` | `0e0ec87de58c` |
| Coordinator (M0) | `packages/zugzwang-runtime/src/zugzwang_runtime/execution/coordinator.py` | `301569e064c4` |
| Contratos (spec) | `packages/zugzwang-core/src/zugzwang_core/spec/` | `a077f79c2c45` |
| Migrations | `packages/zugzwang-runtime/src/zugzwang_runtime/persistence/migrations/versions/` | `98c30ac08449` |

## 2. Matriz baseline — divergências convertidas em tarefas explícitas

| # | Divergência (fonte no PRD) | Estado no baseline | Tarefa explícita | Status |
|---|---|---|---|---|
| D1 | Piso SQLite `3.37.0` em `database.py` e doctor, contra ADR-044/ADR-CB-020; WAL-reset bug afeta 3.7.0–3.51.2, fix 3.51.3, backports 3.44.6/3.50.7 [^R16][^W07] (RISK-13) | Confirmado: `MIN_SAFE_SQLITE = (3,37,0)` e `version >= (3,37)` no doctor | Função única de admissibilidade versionada por linhas corrigidas, compartilhada por bootstrap e doctor, verificando o SQLite efetivamente ligado ao Python; TEST-081 | **Implementado nesta ordem** (§4) |
| D2 | `termination_for()` classifica 75 movimentos como `FIFTY_MOVE` (categoria histórica) [^R03] | Confirmado: `standard.py` — `is_seventyfive_moves()` → `TerminationKind.FIFTY_MOVE` | Renomear categoria e/ou adicionar `SEVENTYFIVE_MOVE` **somente** via mudança deliberada de schema/evento com versão do mapeamento exposta, sem reescrever registros antigos | Diagnóstico emitido (§5); código intocado nesta ordem |
| D3 | Viewer inclui superfície de engine (`stockfish` em `viewer-next/src/lib/localEngine.ts`, `viewer/index.html`) que não pode virar fonte de observação do agente [^R13] | Confirmado: referências presentes | Isolamento planejado (§6); execução pertence ao CB-WO-10 (viewer mínimo causal, ADR-CB-017) | Planejado |
| D4 | Retrievers `frontier`/`refutation` usam correspondência textual e não calculam fronteira/refutação formal [^R06] | Confirmado por auditoria do PRD (§3.2); sem divergência nova encontrada | Elegibilidade antes de ranking (ADR-CB-013) no CB-WO-09 (memória condicionada) | Encaminhado ao CB-WO-09 |
| D5 | `SearchWorkspace` não é tabela completa de transposições; dois nós podem compartilhar posição [^R05] | Semântica atual correta e documentada | Nenhuma — preservar semântica; não "corrigir" para dedup total | Fechado sem ação |

## 3. Snapshot dos schemas atuais

Alembic head: **`0006`** (`0001_initial_schema` → `0006_step_assistance_projection`).
Migrations aplicadas no layout: 0001–0006. Tabelas após upgrade em banco efêmero:

`alembic_version, artifacts, attempts, budget_ledger, checkpoints, episodes,
evaluation_runs, events, experiments, metric_observations, runs, search_edges,
search_nodes, search_retrieval_events, search_sessions, steps` (16).

Nota do PRD (§46.4): não reaplicar o DDL em produção só porque o hash do documento
coincide — este snapshot é registro de leitura, não execução.

## 4. Admissibilidade SQLite corrigida (TEST-081) — implementada

Nova `persistence/sqlite_policy.py` (policy **v2**), única fonte de decisão, usada por
`Database` (bootstrap) e pelo doctor:

- **Admitidas**: 3.x `>= 3.51.3` (mainline corrigida) e branches de backport
  `3.44.6+` / `3.50.7+`. Rejeitadas: intermediárias vulneráveis (3.44.0–3.44.5,
  3.45.0–3.50.6, 3.51.0–3.51.2) e major futura (4.x+) até atualização da política
  com evidência de release (ADR-CB-020: "atualizar a política quando houver nova
  evidência", nunca assumir).
- **Fail-closed**: workspace em arquivo com versão reprovada não abre (default seguro
  do G-CB-04 — nenhum workspace durable em versão reprovada). `:memory:` não exige
  admissão (o bug é específico de WAL em arquivo; §25.1 distingue validação de schema
  de validação operacional).
- **Perfil `ephemeral` explícito** (journal DELETE, `synchronous=OFF`): modo
  não-durável para fixtures/testes, opt-in por workspace (`wal_policy=`) ou via env
  `ZUGZWANG_WAL_POLICY=ephemeral` (decisão operacional explícita, nunca default).
  Locais de teste que abrem banco em arquivo declaram `ephemeral` — a suíte offline
  valida mecânica de persistência/lifecycle, não segurança de WAL (§25.1).
- **Perfil durable** (`synchronous=FULL`/fsync ensaiado): **não implementado** —
  ratificação é G-CB-04 (§48.3). Nenhum gate é ratificado nesta ordem.
- Doctor reporta a decisão com a política na mensagem; acordo doctor/bootstrap
  testado (`tests/unit/test_sqlite_policy.py`, 22 testes).

Ambiente desta máquina: o venv (CPython 3.14.7 via uv) linka SQLite **3.53.1** —
admitida; o SQLite do sistema (3.45.1) seria rejeitado para WAL, ilustrando por que a
política inspeciona a versão efetivamente ligada ao Python e não a do sistema.

## 5. Diagnóstico: nomenclatura de término (D2)

`termination_for()` (`packages/zugzwang-chess/src/zugzwang_chess/environment/standard.py:122`)
aplica corretamente as regras formais (checkmate, stalemate, material insuficiente,
fivefold, 75 movimentos), mas a detecção de 75 movimentos reutiliza a categoria
histórica `FIFTY_MOVE`. O **resultado formal (empate) está correto**; a divergência é
de rótulo. Requisitos para a correção futura (fora do escopo desta ordem): nova
categoria em mudança deliberada de schema/evento, versão do mapeamento persistida nos
eventos, preservação dos registros antigos (sem reescrita silenciosa, §3.5[^R03]) e
atualização de consumers do `TerminationKind`. Encaixa no ciclo de contratos do
CB-WO-02, quando os schemas de eventos forem estendidos.

## 6. Isolamento planejado do viewer (D3)

Superfície atual: `viewer-next/src/lib/localEngine.ts` e `viewer/index.html`
referenciam stockfish. Plano (execução no CB-WO-10, ADR-CB-017 — viewer live sem canal
de aconselhamento do engine): (a) o viewer nunca é fonte de observação do agente —
nenhuma tool lê do viewer; (b) nenhuma avaliação originada no navegador é aceita como
resultado formal — avaliações de engine só via plugin evaluator no processo do kernel;
(c) o viewer passa a consumir apenas snapshots/streams publicados pelo kernel; (d)
build do viewer segregado dos artefatos de evidência (`viewer/data*` já desrastreado
desde a GATE-005). Nenhuma mudança de código nesta ordem.

## 7. Relatório de conflitos de ADR

| Conflito/tenção | Envolvidas | Resolução nesta ordem |
|---|---|---|
| Piso SQLite `3.37` (código) × WAL seguro (ADR-044) — agravado pelo WAL-reset bug documentado em 2026-03 | ADR-044 × `database.py`/doctor | **Resolvido**: política centralizada v2 implementa a intenção da ADR-044 conforme ADR-CB-020; emenda formal da ADR-044 fica para quando o PRD for materializado como ADR de repo |
| ADR-CB-020 (PRD) é decisão **proposta**; implementá-la não a ratifica | PRD §1.2, §40.5 | G-CB-04 permanece pendente: perfil durable não implementado; default seguro aplicado e testado |
| Nomenclatura `FIFTY_MOVE` × regra de 75 movimentos | PRD §3.5[^R03] × código atual | Mantida por enquanto (comportamento legacy preservado e declarado — default do G-CB-06); correção deliberada futura |
| IDs do PRD × numeração do repo | PRD §38.1 ("não assumir que ZGW-0087 está livre") | Mapeamento CB-WO-01 → ZGW-0087 registrado nesta ordem, verificada a liberação do número |

Gates de decisão do repo (`DECISIONS.yaml`): nenhum alterado (12 gates, 6 aceitos,
estados preservados).

## 8. Teste de não alteração das strategies

Suíte offline completa verde após o delta (nenhuma strategy tocada): **264 passed,
1 skipped, 6 deselected** (`uv run pytest -m "not e2e"`), incluindo os testes das
strategies R5/R7, bateria single-agent H1–H5 e os 22 testes novos da política.
`ruff check .`, `ruff format --check .`, `pyright` e `validate_foundation.py --strict`
verdes. `zugzwang doctor` passou a reportar o status honesto da política.

## 9. Limitações

- Os testes SQL rodam em arquivos efêmeros (perfil `ephemeral`) ou em memória; nenhum
  teste da suíte default valida segurança de WAL/fsync/crash-consistency em produção
  (§25.1) — a validação operacional do perfil durable é pós-G-CB-04.
- O snapshot de schemas foi gerado em banco efêmero local; não qualifica o SQLite do
  sistema para WAL de produção (mesmo aviso do PRD para a validação SQL da proposta).
- Diagnósticos D2/D3 não incluiram mudanças de código — são entregas de análise desta
  ordem, com execução encaminhada (CB-WO-02 e CB-WO-10).
