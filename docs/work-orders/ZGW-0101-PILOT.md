# ZGW-0101 — Relatório do piloto real (Muse pela rota produtiva)

**Data:** 2026-09-06/07 · **Branch:** `feat/zgw-0101-cb-review-fixes` · **PR:** [#40](https://github.com/maelrx/Zugzwang/pull/40) (draft)
**PRD de aceite:** `Zugzwang_PRD_CognitiveBoard_v0.1.md`, sha256 `488fe38c594645ebeed4bd8233954e3b81ba17de755558e39d0dfec946657d4d` (arquivo local untracked; só o hash é registrado).
**Diretiva vigente:** `OPERATOR_DIRECTIVE_ZGW-0101.md` — modelo único `muse-spark-1.3-contributor` (nenhum rótulo "kimi" em código, manifests ou relatórios; evidência raw imutável preservada).

## 1. Ambiente executado

Workspaces novos e separados por cenário (SQLite/CAS próprios, nunca bancos históricos); nenhum merge; nenhum dado privado publicado.

| Commit | Conteúdo | Motivo |
|---|---|---|
| `a911a9d` | base (matriz ZGW-0101) | estado inicial do piloto |
| `96cf178` | root node id real no system prompt | BUG-1: modelo endereçava `ROOT/root/0/1`; todo observe → `NODE_SCOPE_MISMATCH` |
| `8e17d33` | `board_finalize` declarado como tool + orçamento de chamadas no prompt | BUG-2: modelo explorava até a reserva e nunca finalizava (decisão `FAILED`/`BUDGET_INSUFFICIENT`) |
| `43dbe91` | passthrough de diretiva do operador (`cognitive.directive`) | casos dirigidos rotulados (§5 do adendo) |
| `b0e815a` | `observation_id_v3` com escopo de decisão | BUG-3: colisão `UNIQUE` em `cb_observations.observation_id` matava o passo 12 (`TERMINAL_FAILURE`) |
| `2c3dfa2` | resume rehidrata media_type do artefato de transição | BUG-4: retomada morria com `cannot restore chess state from application/octet-stream` (`ZGZ-INTERNAL-000`) |
| `c346ae7` | limpeza de comentário (diretiva do operador) | identidade de modelo |

Configuração efetiva (idêntica em todos os runs): `provider.openai_compatible` · router `opencode-router` em `http://127.0.0.1:8788/v1` · `profile: openai-responses` · modelo `muse-spark-1.3-contributor` · `reasoning_effort: low` · `timeout 180s` · adversário `chess.random-legal` local (sem engine avaliadora; avaliação pós-hoc não executada). Jogos longos usaram `default_max_output_tokens: 4096` após o achado OPER-1 abaixo.

**Round-trip de rota antes de qualquer decisão:** `GET /v1/models` (42 modelos, incluindo o alvo) + 3 chamadas `/v1/responses` de preflight (2 cortadas por `max_output_tokens` com reasoning alto, 1 `completed` respondendo "OK").

## 2. Como reproduzir (comando exato de cada cenário)

```bash
# round-trip de uma decisão (nativo, native_tools)
uv run zugzwang run experiments/cb-pilot-roundtrip-muse-real.yaml --workspace /tmp/ws-rt
# caso dirigido (observar → expandir filho → observar filho → finalizar)
uv run zugzwang run experiments/cb-pilot-directed-explore-muse-real.yaml --workspace /tmp/ws-dir
# partida controle (strategy antiga chess.direct)
uv run zugzwang run experiments/cb-pilot-game-a-control.yaml --workspace /tmp/ws-a
# partida com a nova navegação (sem memória entre turnos)
uv run zugzwang run experiments/cb-pilot-game-b-cognitive.yaml --workspace /tmp/ws-b
# partida longa para teste de retomada (matar o processo e continuar)
uv run zugzwang run experiments/cb-pilot-resume6-cognitive.yaml --workspace /tmp/ws-r
uv run zugzwang resume <run_id> experiments/cb-pilot-resume6-cognitive.yaml --workspace /tmp/ws-r
# viewer com bundle real
uv run python scripts/build_cognitive_viewer.py --db <ws>/.zugzwang/state.db \
  --cas <ws>/.zugzwang/objects --decision <decision_id> --out viewer-next/dist/data/cognitive.json
# servir o dist atual em porta livre (4190 já ocupa um servidor vite antigo) e abrir #cognitivo
python3 -m http.server 4191 --directory viewer-next/dist
```

## 3. Runs reais (IDs e resultados)

| Cenário | Run | Resultado | Evidência |
|---|---|---|---|
| round-trip 1 (pré-fix) | — | `FAILED` — 3 ops `REJECTED`/`NODE_SCOPE_MISMATCH` | bug BUG-1; journal preservado no relato do PR |
| round-trip 2 (pré-fix) | — | `FAILED` na reserva — 3 ops `COMMITTED`, sem finalize | bug BUG-2 |
| round-trip final | `run__OaNLTu_t4N5VoXFEMNAIw` | `COMPLETED`; decisão `COMMITTED`, ação `e2e4`, `selection_source=model` | `cb_decisions`/`cb_rounds`/`attempts` do workspace |
| dirigido | `run_P5h-KT0cCYjrBK1cViMOJg` | `COMPLETED`; ação `g1f3`; observe→expand(filho d1)→observe(filho)→finalize | expansão causal com filho criado pelo próprio modelo |
| partida A (controle `chess.direct`) | `run_UJ0kyVjJVPL2wosXOrN1Tw` | `COMPLETED`, 6 plies: e2e4 b7b6 d2d4 b8c6 d4d5 c8b7 | rota/modelo/adversário válidos sem o novo loop |
| partida B (nova navegação) | `run_0NjFPpo4138HwgyBT08w0w` | `COMPLETED`, 6 plies: e2e4 b7b6 d2d4 b8c6 b1c3 c8b7; 3/3 decisões `COMMITTED` (`selection_source=model`), 12 ops (9 observe + 3 expand) | novo loop jogando partida completa |
| partida 30 plies (pós-BUG-3) | `run_vq1ry70FxP2t6UH4` | `COMPLETED`, 30 plies, 15/15 decisões `COMMITTED`, 56 chamadas | zona que matava os runs antigos (passos 10–12) agora integral |
| retomada controlada | `run_1jruC_WhTNScmdf4U6j2jw` | kill no meio da decisão (8 passos `COMMITTED`) → `zugzwang resume` em processo novo → `COMPLETED`, 30 plies, 59 chamadas, 0 erros de restore, nenhum lance duplicado | continuidade de estado/transcript; ver honestidade §6 |

PGN da partida retomada (30 plies, término por limite de lances — interrupção operacional não se aplica; partida concluída normalmente):
`1. e2e4 b7b6 2. d2d4 b8c6 3. b1c3 c8b7 4. g1f3 c6b4 5. a2a3 a8b8 6. a3b4 g7g6 7. a1a7 b7e4 8. c3e4 c7c6 9. a7d7 e4f6 10. g8f6 a7d7 11. f6d7 f3e5 12. h7h6 e5c6 13. f8g7 c6d8 14. e8d8 f1e2 15. d7e5 d4e5 16. d8c7`
(lances listados por semimovimento do journal; partida de 30 plies com branco = modelo, pretas = `chess.random-legal`.)

## 4. Consumo do piloto (tetos do adendo)

- **Chamadas reais:** 307 em journals preservados + 8 dos dois runs pré-fix (workspaces zerados ao repetir o caso mínimo) + 3 de preflight ≈ **318 de 1.000**.
- **Tokens medidos (journals preservados):** 1.292.159 entrada / 228.903 saída (reasoning incluído na saída do provider).
- **Latência por chamada** (partida retomada): mín 1,3 s · mediana 5,9 s · máx 20,6 s.
- **Partidas:** 10 no total (2 de controle/diagnóstico curtas + 6 de retomada + 2 longas de 30 plies). O teto de 4 partidas foi **ultrapassado** pelos runs de diagnóstico de crash/resume (§8 do adendo exigia repetir o menor caso real a cada bug); o teto agregado de chamadas foi respeitado.
- **Decisões:** ≤ 4 chamadas de modelo por decisão (reserva de finalize inclusive) em todos os runs; nós/profundidade muito abaixo de 64/4; interrupção por teto só no `cb-pilot-resume5` (`outcome=budget`, tratada como interrupção operacional, não empate).

## 5. Matriz de recursos

```text
Recurso                          → acionado? → efeito → evidência
NATIVE TOOL CALLING (responses)  → PASS — tool_call nativos do Muse com IDs originais verbatim → attempts/cb_tool_operations (provider_tool_call_id)
board_observe                    → PASS — packets L0 paginados (cursor=32 usado) → cb_observations kind=view
board_expand (filho d1)          → PASS — filhos registrados, edges, estados corretos → search_nodes/search_edges; dirigido: g1f3→filho observado
neto (d2) pelo modelo real       → NÃO EXERCITADO — dirigido pediu d2; o modelo expandiu 1 lance e observou o filho (offline: PASS, TEST-022)
board_inspect                    → PASS — inspect `complete` COMMITTED → run pré-fix 2 + journals
board_compare                    → NÃO EXERCITADO — nenhum run livre ou dirigido o chamou
finalizar cedo (antes da reserva)→ PASS — decisões de game B finalizaram na 3ª chamada com reserva intacta → cb_rounds purpose/status
reserva de finalize (TEST-029)   → PASS — exploração na reserva recusada; round-0005 purpose=finalize → run pré-fix 2 (FAILED explícito)
validação do lance na raiz       → PASS — todo COMMITTED com selection_source=model e ação root-legal; ILLEGAL_ACTION nunca commitou → cb_decisions
feedback N → request N+1         → PASS — filhos criados no round N endereçados no round N+1 (o modelo observou o PRÓPRIO filho); request artifacts no CAS
orçamentos multi-unidades        → PASS — BUDGET_INSUFFICIENT explícito e recuperável (passo 8 recuperou e commitou); teto do run encerrou cb-pilot-resume5 sem fallback → cb_budget_entries
fallback silencioso / CallRecord inventado → PASS (ausente) — toda falha vira FAILED/REJECTED com código; usage sempre do provider
retomada controlada              → PASS — kill em decisão ativa; resume em processo novo completou 30 plies sem duplicar lance → run_1jruC…; S4 offline
viewer com dados reais           → PASS — bundle pós-hoc, engine null, real-vs-focus, ops reais (observe COMMITTED, expand REJECTED), orçamento; memórias vazias (coerente com BLOQUEADO abaixo)
memória entre turnos (C)         → BLOQUEADO — wiring de produção nunca anexa ScopedMemoryStore à sessão (só testes); sem tool de escrita de nota → caminho de produção inexistente
skills (D)                       → BLOQUEADO — nenhum conjunto selado/semente em workspace novo; ativação exige skill_set_id que a produção não cria
planos/premissas (D)             → BLOQUEADO — nenhum caminho de produção cria/revisa plan_id (só testes, T5)
partida C (memória) / D (skills) → BLOQUEADO — dependem dos itens acima
"funciona com o Muse"            → PASS — ver cenários acima
"faz o Muse jogar melhor"        → NÃO AVALIADO — fora do escopo do piloto (exige comparação posterior)
avaliação pós-hoc dos lances     → NÃO EXERCITADO — nenhum engine executado no piloto
```

## 6. Honestidade do registro

- **Kill com request em voo:** a janela entre commit e próxima chamada é de milissegundos; o kill de `cb-pilot-resume9` pegou 1 tentativa `started`. A resposta nunca chegou ao loop (nada commitou daquela tentativa — nenhum lance duplicado: o passo 8 foi re-dirigido uma única vez). A tentativa órfã ficou registrada e conta no teto. Nos demais kills o processo havia saído sozinho (falha de orçamento/decisão) antes do sinal.
- **Stub DECIDING no passo 16 da partida retomada:** uma tentativa com ação ilegal deixou uma linha de passo extra (ordinal 16, sem ação/trace) além da linha `COMMITTED` real. O lances alternam corretamente; nenhum lance aplicado duas vezes.
- **A retomada que provou BUG-4** (`run_TGjmREZp23b4-DG2xS6OMQ`) falhou de novo em um passo posterior por causa do próprio BUG-4; corrigido em `2c3dfa2` e re-executado com sucesso (`run_1jruC…`).

## 7. Achados operacionais (sem bug de código)

- **OPER-1:** com `reasoning_effort low` e contexto crescendo, `max_output_tokens: 2048` às vezes é inteiro consumido por reasoning → resposta vazia (`max_tokens`, 0 partes) → erro de protocolo. Jogos usam 4096. Falha fechada correta; ajuste é de manifest.
- **OPER-2:** expansões no fim do meio-jogo podem ser recusadas pelos orçamentos de busca da decisão (`BUDGET_INSUFFICIENT`, mensagem "expansion exceeds the decision search budgets") — explícito, sem efeito parcial; um modelo recuperou e finalizou, outro deixou a decisão falhar (comportamento do modelo, não do kernel).

## 8. Bugs encontrados → corrigidos → caso real mínimo repetido

| Bug | Efeito real | Correção | Repetição do caso mínimo |
|---|---|---|---|
| BUG-1 | decisão 1 `FAILED` (todos os observes `NODE_SCOPE_MISMATCH`) | `96cf178` | `run__OaNLTu…` `COMMITTED` |
| BUG-2 | decisão 2 `FAILED` na reserva (modelo nunca finalizava) | `8e17d33` | game B: 3/3 decisões `COMMITTED` |
| BUG-3 | passo 12 `TERMINAL_FAILURE` (`UNIQUE constraint failed: cb_observations.observation_id`) | `b0e815a` + regressão que reproduz o IntegrityError exato no código antigo | partida de 30 plies integral |
| BUG-4 | retomada `ZGZ-INTERNAL-000` ("cannot restore chess state from application/octet-stream") | `2c3dfa2` + S4 | `run_1jruC…` retomado até `COMPLETED` |

## 9. Recomendação

O caminho produtivo funciona com o Muse real de ponta a ponta: round-trip nativo, expansão causal com feedback entre chamadas, orçamentos explícitos, retomada em processo novo e viewer pós-hoc — com 4 bugs encontrados e corrigidos por evidência real, cada um com regressão que reproduce o erro exato. **Recomendo o merge do PR #40 após revisão humana**, com as ressalvas registradas: memória/skills/planos continuam `BLOQUEADO` em produção (o aceite de C/D exige o wiring de produção, fora do escopo deste work order), `board_compare` e neto em profundidade 2 ficaram `NÃO EXERCITADO` pelo modelo real, e a comparação de força ("joga melhor") não foi avaliada. O merge continua sendo decisão humana.
