# ZGW-0101 — Matriz requisito → implementação → teste → evidência → status

PRD: `Zugzwang_PRD_CognitiveBoard_v0.1.md` (untracked por política local;
`sha256:488fe38c594645ebeed4bd8233954e3b81ba17de755558e39d0dfec946657d4d`).
Snapshot revisado: `a2d0241`. Branch de correção:
`feat/zgw-0101-cb-review-fixes` (empilhada no head da stack, sem merge).

Status permitidos: entregue · parcial · scaffold · bloqueado · não implementado.
Regra aplicada: nenhuma WO marcada completa com capacidade essencial deferida.

## T1 — Expansão real (FR-002/003/008/009/010; TEST-005/006/009/014/077/078)

| Requisito | Implementação produtiva | Teste concreto | Evidência | Status |
|---|---|---|---|---|
| FR-009 expandir qualquer nó acessível (≥3 plies) | `broker._expand` via SearchWorkspace+RulesKernel; `register_child_node` transacional | `test_expand_transitions_and_child_is_observable_and_expandable` (e2e4→c7c5, neto, FENs) | journal: bindings depth 0/1/2 + arestas | entregue |
| FR-002 conjunto legal completo paginado | `_full_legal_index` sobre o kernel (todas as páginas) | `test_expand_resolves_action_from_any_page` (page_size=5, ação da pág. 3) | — | entregue |
| FR-010 sem transição após término | guarda `parent.terminal` | `test_expand_terminal_node_is_refused` (mate f3/e5/g4/Qh4#) | — | entregue |
| TEST-006 ação de outro estado | resolução por state_key | batch com id estranho → ACTION_STATE_MISMATCH sem efeito parcial | `test_expand_batch_with_foreign_action_has_no_partial_effect` | entregue |
| INV-03 transposição preserva trajetória | workspace try_move + nó novo por trajetória | `test_expand_reaches_transposition_without_losing_trajectory` (Nf3/Nf6/Ng1/Ng8) | stats.transpositions ≥ 1 | entregue |
| §42.6 queries físicas reais | `_packet_query_count` + stats do workspace | `test_expand_reports_real_physical_rules_queries` | — | entregue |

## T2 — Loop produtivo (FR-011/012/013; TEST-022/023/024/025/028/029/030)

| Requisito | Implementação produtiva | Teste concreto | Evidência | Status |
|---|---|---|---|---|
| FR-011 loop adaptativo; tool result na próxima chamada | `CognitiveLoop.run()` chama `backend.infer` com transcript real | fake extrai child_node_id do request N+1 | `test_multi_round_observe_expand_grandchild_finalize`, `test_causal_feedback_visible_in_request_n_plus_one` | entregue |
| FR-012 finalizar só na raiz real | `_finalize` valida contra root + `resolve_action` | `test_finalize_at_wrong_focus_rejected` | — | entregue |
| TEST-025 seleção antecipada | finalize encerra as rounds | `test_early_selection_preserves_budget` | — | entregue |
| TEST-029 reserva de finalização | reserva em MODEL calls; round reservado recusa exploração | `test_exploration_never_spends_finalize_reserve` | — | entregue |
| Integração strategy/factory/coordinator/manifest | ramo `chess.cognitive_navigation` nos coordinators; factory em DurableRunServices; entry point builtin; golden YAML | `test_cb_navigation_strategy.py` + `tests/e2e/test_cb_golden_offline.py` + CLI `cognitive-golden-offline.yaml` → COMPLETED | run COMPLETED, decision COMMITTED e2e4/model | entregue |
| Descriptor conservador (G-CB-01 pendente) | R7/H4/K0 em `navigation.py` | `test_descriptor_stays_conservative_until_gate` | — | entregue |

Deferrado (dono: runtime; impacto: nenhum requisito essencial some):
scripts continuam existindo SOMENTE em backends fake (`FakeCognitiveBackend`).

## T3 — Contratos, IDs e providers (FR-014; TEST-021/026/027/065)

| Requisito | Implementação produtiva | Teste concreto | Evidência | Status |
|---|---|---|---|---|
| TEST-026 IDs originais preservados | `provider_tool_call_id` do modelo → operation row + envelope meta | `test_provider_ids_survive_full_composition` (call_7/call_8 via MockTransport) | journal `provider_tool_call_id` | entregue |
| TEST-021 schema do resultado antes de COMMITTED | `_validate_payload` por tool | `test_invalid_payload_settles_failed_not_committed` (injeção, não exceção) | status FAILED + sem exposição | entregue |
| TEST-027 native vs JSON, mesmo efeito | `_parse_proposals` + `_resolve_json_arguments` | `test_json_commands_same_effect_distinct_mode`, `test_route_profiles_same_effect_distinct_wire` | endpoints /chat/completions vs /responses | entregue |
| Capability gate via `infer()` | `RecordingBackend.infer` recusa antes do transporte | `test_recording_backend_capability_gate_refuses_before_wire` (inner.calls == 0) | — | entregue |

## T4 — Budgets, transação e recuperação (FR-015/016/017/018/019; TEST-029/031/032/034/036/037/038/040/041)

| Requisito | Implementação produtiva | Teste concreto | Evidência | Status |
|---|---|---|---|---|
| Unidades distintas (§13) | `DecisionBudget` (tool_operations + model_calls); reserva no open; débito por infer | matriz de orçamento + golden (`model_calls` 4/3, `tool_operations` 32/2) | `cb_budget_entries` | entregue |
| Reserva final de inferência | loop impõe em rounds, não em ops de board | TEST-029 acima | — | entregue |
| Pré-validação sem falha no settlement | `_charge_clamped` | `test_budget_error_matrix_and_idempotent_retry` (saldo zero: REJECTED, sem ValueError, sem PREPARED órfão) | — | entregue |
| Sem atomicidade prometida entre CAS e SQLite | protocolo explícito: artefato→transação SQL única (settle+exposição+ledger) | `settle_tool_operation_with_exposure` | — | entregue |
| `resume_decision` reconstrói | nós+FENs+transcript+rounds+budgets+PREPAREDs; `resume_session` continuável | S1 (crash mid-decision → resume → COMMITTED em processo novo) | — | entregue |
| Kill/restart em processo novo | filhos com `os._exit` nos pontos de falha | S1/S2/S3 em `test_cb_crash_recovery.py` | subprocessos reais, disco temporário | entregue |
| Gate CB-WO-08 | `run_class: disposable-smoke`; research-ready recusado por omissão | validador do manifest | — | entregue |

## T5 — Memória, snapshots, skills e planos (FR-024..033; TEST-042..051/075)

| Requisito | Implementação produtiva | Teste concreto | Evidência | Status |
|---|---|---|---|---|
| TEST-044 elegibilidade antes de ranking | ordem scope→validity→kind→perspective→partition→epistemic, sem atalho test | `test_eligibility_matrix_no_early_return_for_test_partition` | matriz ± | entregue |
| TEST-045 restore sem lavagem | sem defaults inventados; validade viaja; origem desconhecida recusada; hash 64-hex | `test_restore_preserves_quarantine_and_refuses_unknown_origin` | — | entregue |
| Congelamento de bindings (0009) | trigger `cb_decision_late_binding`; upgrade idempotente; downgrade recusa antes de DDL | `test_migration_0009_freezes_bindings_and_round_trips` | triggers + round-trip | entregue |
| Memória/skills/planos no contexto real | seção do system prompt a partir dos stores; feedback revisa plano | `test_cb_context_wiring.py` (3 testes sobre `seen_requests`) | requests efetivos | entregue |

## T6 — Viewer e análise (FR-035/037/038; TEST-058/059/060/061/066)

| Requisito | Implementação produtiva | Teste concreto | Evidência | Status |
|---|---|---|---|---|
| Export sem tocar a fonte | `Database(read_only=True)` + exporter read-only | `test_readonly_export_never_touches_source` (bytes idênticos, escrita recusada) | — | entregue |
| CognitiveTimeline montada com bundle real | rota #cognitivo + `useCognitiveBundle` + snapshot enriquecido | `test_exporter_snapshot_loads_real_bundle` + `tests/cognitive.test.mjs` (13) + `tsc+vite build` | FENs/raiz/operações/budget reais | entregue |
| Separação post-hoc/live; sem engine no live | loader recusa mode≠post_hoc/engine≠null; LiveEval opt-in default OFF | teste de recusa no .mjs | — | entregue |
| Custos honestos (CB-01) | total_off/total_on/delta; rejeição de métricas ausentes/não-finitas | `test_missing_or_nonfinite_metrics_are_rejected_not_zeroed` | `pairs_unknown_metric` | parcial (runner/CLI da ablação seguem pendentes; preparação ≠ bateria) |

## Status honesto por WO

| WO | PR | Status | Capacidade essencial |
|---|---|---|---|
| CB-WO-01 | #25 | entregue | baseline + TEST-081 |
| CB-WO-02 | #27 | entregue | contratos/ports/estados |
| CB-WO-03 | #28 | entregue | percepção/deltas |
| CB-WO-04 | #29 | entregue | journal CB-M1 |
| CB-WO-05 | #30 | parcial→entregue após T1 | broker real (era scaffold de expand) |
| CB-WO-06 | #31 | parcial→entregue após T3 | round-trip com IDs e validação |
| CB-WO-07 | #32 | parcial→entregue após T2 | loop produtivo integrado |
| CB-WO-08 | #33 | parcial→entregue após T4 | durabilidade testada em processo novo; gate smoke restaurado |
| CB-WO-09 | #34 | parcial→entregue após T5 | elegibilidade + contexto real |
| CB-WO-10 | #35 | parcial→entregue após T6 | timeline roteada com bundle real |
| CB-WO-11 | #36 | parcial | análise honesta; bateria (runner/CLI) pendente |
| CB-WO-12 | #37 | parcial→entregue após T5 | skills seladas + ativação no request |
| CB-WO-13 | #38 | parcial→entregue após T5 | planos revisados pelo delta real |
| CB-WO-14/15 | — | não implementado | gates humanos preservados |

## Achado → commit → teste → artefato

| Achado (revisão a2d0241) | Commit | Teste | Artefato |
|---|---|---|---|
| `_expand` fabricava expanded=True | 193749a (T1) | 6 probes em test_cb_tool_broker | bindings/arestas/FENs |
| `run(script)` sem backend | 349bad6 (T2) | test_cb_navigation_loop reescrito + strategy | golden CLI COMPLETED |
| IDs sintéticos; COMMITTED sem schema | 294226d (T3) | full_composition + payload injection | journal provider_tool_call_id |
| Janela COMMITTED sem débito; saldo-zero ValueError; resume só contadores | b73b491 (T4) | test_cb_crash_recovery (S1/S2/S3) | subprocessos + run_class |
| `_eligibility` atalho test; restore inventava; 0009 furada; contexto isolado | eabf9d7 + 45c3d4a (T5) | matriz + restore + 0009 + context_wiring | requests efetivos |
| Exporter DELETE na fonte; timeline morta; custo somado | 70f5ea5 (T6) | readonly bytes + cognitive.test.mjs + ablation | build + snapshot real |
| Checklist/handoffs diziam neto/causal/resume provados | este T7 | golden e2e + CI verde | checklist PR #26 corrigido |

## CI no snapshot revisado

- `uv sync --all-packages --all-extras --locked` ✓
- `uv run ruff check .` ✓ · `uv run ruff format --check .` ✓
- `uv run pyright` ✓ (0 errors)
- `uv run pytest -m "not e2e"`: 424 passed, 1 skipped ✓
- `uv run pytest -m e2e`: golden 2 passed; `test_real_stockfish_posthoc_evaluation` FALHA — pré-existente no a2d0241 (verificado por stash), depende de engine real, sem relação com ZGW-0101
- `uv run python scripts/validate_foundation.py --strict`: falha em `viewer-next/public/engine/*.wasm` (binários ignorados do setup-engine; controle de caracteres do validador) — pré-existente, fora do escopo
- viewer-next: `npm run build` (tsc+vite) ✓ · `npm test` 13/13 ✓ · `npm run lint` ✓

## Plano de restack e merge (humano, após revisão)

Topologia preservada: #25/#26/#27 partem de main; #28..#38 em cadeia;
#29 incorpora #25. Nenhum merge em lote por ordem numérica.

1. Congelar heads atuais (sem force-push; sem merge).
2. Revisão humana da branch `feat/zgw-0101-cb-review-fixes` (este trabalho).
3. Após aprovação: rebase da stack WO por WO sobre main, aplicando os
   patches T1–T7 nas respectivas WOs (#30←T1, #31←T3, #32←T2, #33←T4,
   #34/#37/#38←T5, #35/#36←T6), com CI do conjunto exato por PR.
4. Só então merge human-reviewed, um PR por vez, na ordem de dependência
   (#25, #26, #27, #28 … #38).
5. G-CB-01..08 e CB-WO-14/15 intocados: nenhum gate ratificado por agente.
