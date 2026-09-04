# Zugzwang v0.1 — Agentic Build Checklist (sessão determinística)

Roadmap operacional da sessão de build do v0.1. Governa o loop agêntico e permite retomada segura: **nenhum item é marcado `[x]` sem evidência de comando executado; nenhum passo commitado é refeito; nada é pulado silenciosamente.**

## Protocolo do loop

1. Trabalhar um item por vez, na ordem.
2. Rodar o teste/gate de verificação do item.
3. Marcar `[x]` no arquivo E no todo list da sessão somente após o gate passar.
4. Se um gate falhar: corrigir e re-rodar o MESMO item (não avançar).
5. Se um gate exigir decisão humana: parar e preparar packet (skill `prepare-human-decision-gate`).
6. No final de cada milestone: rodar `python scripts/validate_foundation.py --strict` + suite offline.
7. Nunca: provider real, rede em testes, engine real nos gates, LICENSE nova, decisão de gate pendente.

## Legenda

- `[x]` concluído com evidência · `[~]` em andamento · `[ ]` pendente

---

## P0 — Ratificação e registro (pré-condição)

- [x] GATE-001 ratificado (GPL-3.0-or-later + python-chess) → DECISIONS.yaml, ADR-004, DECISION_LOG, LICENSE, LICENSE-DECISION
- [x] GATE-002 ratificado (Python >=3.13, CI 3.13/3.14) → DECISIONS.yaml, ADR-003, DECISION_LOG
- [x] GATE-004 ratificado (`zugzwang` + `zgw`) → DECISIONS.yaml, ADR-037, DECISION_LOG
- [x] `python scripts/validate_foundation.py --strict` verde (PASS 9, 0 errors)
- [x] Python 3.13.14 disponível via uv (instalado: 3.13.14)

## M0 — Constituição do kernel (exit: vertical slice fake + architecture tests + schemas estáveis)

Workspace e tooling:
- [x] `pyproject.toml` raiz: uv workspace (`packages/*`, `plugins/*`), requires-python >=3.13, dev deps (pytest, pytest-cov, hypothesis, ruff, pyright)
- [x] `uv.lock` gerado com Python 3.13 (`uv lock` / `uv sync`)
- [x] Config ruff/pyright/pytest/coverage no pyproject raiz
- [x] `packages/zugzwang-core/pyproject.toml` + `src/zugzwang_core/` (sem deps além de pydantic)
- [x] `packages/zugzwang-runtime/pyproject.toml` + `src/zugzwang_runtime/`
- [x] `packages/zugzwang-chess/pyproject.toml` + `src/zugzwang_chess/` (deps: zugzwang-core, python-chess)
- [x] `packages/zugzwang-cli/pyproject.toml` + `src/zugzwang_cli/` (entry points `zugzwang` + `zgw`)
- [x] `plugins/*/pyproject.toml` + módulos de plugin mínimos (entry points por grupo)

Domínio (zugzwang-core):
- [x] ids (run/episode/step/attempt/event/artifact) + validação de prefixo
- [x] clocks (utc, monotonic) e timestamps
- [x] money decimal + usage (input/output/total tokens, source estimated|provider)
- [x] schema_versions (zgw.manifest/v1alpha1, zgw.event/v1alpha1, zgw.bundle/v1alpha1, zgw.plugin/v1alpha1)
- [x] error taxonomy (categorias §26.4: CONFIGURATION..INTERNAL) com stable codes
- [x] event envelope Pydantic strict + sequence por stream
- [x] assistance classes H0–H7 + K-axis + agregação effective_assistance
- [x] manifest v1alpha1: source → resolved (Pydantic strict), patches (`--set /spec/...`)
- [x] canonical hashing (JSON canônico + SHA-256) determinístico
- [x] matriz `product`/`zip` com IDs estáveis por condição
- [x] ports: ModelBackend, Environment, Evaluator, DecisionStrategy, Tool (Protocols)

Fakes:
- [x] DeterministicModelBackend (script por call_index/fingerprint)
- [x] fake environment (counter) para provar core sem chess
- [x] fake evaluator idempotente com provenance

Runtime mínimo:
- [x] application services: ValidateManifest, ResolveExperiment, PlanExperiment, StartRun (in-memory)
- [x] executor fake de 1 episode/1 step emitindo eventos + artifact pequeno
- [x] CLI: `init`, `doctor`, `schema export`, `experiment validate`, `experiment plan`, `run` (fake), `--output json/human`

Schemas e contratos:
- [x] geração de JSON Schemas a partir dos modelos Pydantic; comparar com `schemas/*.schema.json` draft
- [x] `tests/architecture/` proibindo imports inválidos (core sem pydantic-ai/sqlalchemy/chess/typer/httpx)
- [x] `tests/contract/` harness para ModelBackend/Environment/Evaluator
- [x] `tests/unit/` domínio + canonical hash + matriz
- [x] CI workflow offline (`.github/workflows/ci.yml`)
- [x] vertical slice: `zugzwang run experiments/fake-smoke.yaml` (fake) → eventos + artifact + hash

Exit M0:
- [x] `uv run pytest -m "not e2e"` verde
- [x] `uv run ruff check .` + `uv run ruff format --check .` verdes
- [x] `uv run pyright` verde (strict nos pacotes principais)
- [x] `python scripts/validate_foundation.py --strict` verde (PASS 9, 0 errors)
- [x] README atualizado com comandos reais

## M1 — Execução local mínima (exit: crash injection prova que step commitado não repete)

- [x] SQLite WAL + SQLAlchemy 2 Core + Alembic migrations (tabelas §11.3)
- [x] CAS filesystem (SHA-256, sharding, escrita atômica, dedup) com protocolo de commit §10.5
- [x] PersistenceWriter único com bounded queue + backpressure
- [x] event stream append-only: envelope, sequence por stream, projection na mesma transação
- [x] state machines run/episode/step (§10.3/§10.4) com transições inválidas rejeitadas
- [x] budgets: max_calls, max_input/output/total_tokens, max_usd, max_wall_time, max_failed_calls, max_attempts, timeout; ledger reserve/reconcile
- [x] rate limiting in-process (semáforos/token buckets por backend/modelo)
- [x] interrupt (Ctrl-C) → checkpoint consistente; `resume <run-id>` sem repetir committed steps
- [x] attempts: retry taxonomia (transport/throttling/5xx/timeout/parse/illegal), outcome_unknown em timeout ambíguo
- [x] `tests/fault/` crash injection nos 12 pontos §24.1
- [x] `tests/integration/` SQLite+CAS, migrations, run com fake provider, interrupt/resume, bundle export/import

Exit M1:
- [x] fault suite verde: recovery não aplica ação 2x nem cria dangling refs
- [x] `resume` de run interrompido reproduzido em teste
- [x] gates M0 continuam verdes

## M2 — Xadrez formal (exit: nenhuma ação ilegal em fuzz/random walks/fixtures raras)

- [x] ChessGameState integral (posição, lado, roque, en passant, halfmove, fullmove, histórico p/ repetição, termination)
- [x] action codec UCI canônico; SAN como codec de interface (registra `+/#`)
- [x] legal actions: conjunto ordenado estável + hash + encoding (uci|opaque_index) + leakage annotations
- [x] transition determinística; rejeição de ação ilegal (categoria distinta de parse error)
- [x] FEN codec + state fingerprint; observation policies (fen/ascii/history/legal exposure)
- [x] tasks: MoveSelectionTask, FullGameTask (termination/resultado formais), StateReconstructionTask (exact/auxiliary)
- [x] opponents: random legal com seed, scripted/replay, adapter de DecisionStrategy, UCI engine opponent (com FakeUciEngine)
- [x] PGN mainline export estrito (próprio e pequeno, sem parser rico)
- [x] suites: openings pareadas (cores invertidas), pair IDs
- [x] perft positions clássicas (depth 1–4 em subset) + FEN/UCI roundtrip + property random walks
- [x] fixtures raras: underpromotion, en passant expondo check, castling through attack, repetição, insufficient material

Exit M2:
- [x] `uv run pytest tests/unit tests/contract -m "not e2e"` (chess) verde
- [x] perft suite verde; nenhuma ação ilegal aplicada
- [x] replay determinístico de episódio chess (fake provider)

## M3 — Providers e R0–R2 (exit: contract suite comum passa em fake + 2 adapters sem rede no CI)

- [x] ModelBackend port + canonical request/response (wire_fidelity, usage com fonte, requested/reported model)
- [x] capability negotiation (required/preferred/on_unsupported: fail|emulate|degrade)
- [x] plugin provider-openai-compatible: httpx direto, profiles, base URL confiável, raw fidelity, contract tests com servidor HTTP local fake
- [x] plugin provider-pydantic-ai: Direct Model Requests atrás do contrato (sem Agent loop); tipos não escapam do plugin
- [x] retry policy explícita (transport/parse/illegal) com attempts distintos e eventos
- [x] strategies: DirectStrategy (R0), GroundedStrategy (R1), RepairStrategy (R2) com DecisionTrace completo
- [x] output codecs: extração JSON, validação estrutural, normalização UCI/SAN/index, parse_success vs legal
- [x] PromptProgram versionado (template ID/version, render, SHA-256, token estimate)
- [x] raw artifacts: request/response preservados no CAS; secrets nunca entram
- [x] contract suite rodando contra os 3 backends (fake, openai-compatible local, pydantic-ai mock)

Exit M3:
- [x] contract suite verde nos 3 backends offline
- [x] R0/R1/R2 rodam end-to-end com fake backend em episódios chess
- [x] gates M0–M2 continuam verdes

## M4 — R3, avaliação e bundles publicáveis (exit: bundle exportado numa máquina é importado e reavaliado offline em outra)

- [x] StructuredStrategy (R3): analyze→propose→simulate→estimate→choose→verify, chamadas separadas ou única structured response (manifesto diferencia)
- [x] evaluator-stockfish: processo UCI externo, limites (depth/nodes/movetime), MultiPV, cache por chave rigorosa, transcript; pós-hoc por padrão
- [x] FakeUciEngine completo para testes offline
- [x] metrics registry: MetricDefinition (id, versão, scope, unit, direction, requires, formula_artifact) + MetricObservation (provenance)
- [x] métricas operacionais (latency/calls/tokens/retries/failures/custo) e enxadrísticas (outcome, legal rate, CPL/ACPL, blunders, fase)
- [x] assistance: declared vs effective por run; protocol violation quando H declarado < observado
- [x] finalização materializa Parquet (runs/episodes/steps/attempts/metrics/events) + consulta DuckDB
- [x] reporter-parquet plugin + relatório Markdown + resumo terminal + JSON summary
- [x] run bundle (§11.8) com checksums.sha256; export/import com validação de schema+checksums; replay offline (parse/transição/avaliação sem provider)
- [x] estatística pareada (bootstrap por pares/openings) básica
- [x] GC segura (remove apenas objetos não referenciados após grace period)

Exit M4:
- [x] teste de roundtrip: export em tmp → import em outro workspace → reavaliar offline
- [x] `zgw evaluate`, `zgw report`, `zgw export`, `zgw import`, `zgw replay` funcionais com fakes
- [x] gates M0–M3 continuam verdes

## M5 — Robustez de plataforma (exit: instalação limpa roda smoke local; CI offline cobre fault paths)

- [ ] discovery de plugins por entry points (importlib.metadata, lazy-load, rejeição de plugin_api incompatível)
- [ ] plugin descriptors (id, versão, plugin_api, kind, config_schema, capabilities, license, trust, isolation)
- [ ] `zgw plugins list/inspect`, `zgw providers list/inspect/test`
- [ ] redaction policies (none/standard/strict) com declaração no bundle
- [ ] secret references (`env:`, redigidos de events/resolved manifest)
- [ ] tool allowlist + rejeição de tool calls não permitidas (eventos de segurança)
- [ ] `zgw doctor` completo (dangling refs, órfãos, migrations, engines) e `zgw gc`
- [ ] fault injection suite completa (12 pontos) + compatibility fixtures + event upcasters
- [ ] SBOM (CycloneDX) exportável; lockfile com `--locked` no CI
- [ ] exit codes estáveis documentados; `--yes` para destrutivos; sem prompt interativo em CI

Exit M5:
- [x] `python scripts/validate_foundation.py --strict` verde (PASS 9, 0 errors)
- [ ] CI offline completo verde; SBOM gerado
- [ ] smoke limpo: `uv run zugzwang doctor` + run fake em workspace novo

## M6 — Primeira suite científica (exit: bundles/docs permitem a terceiros reproduzir processamento e entender diferenças de protocolo)

- [x] experiments/: protocolos R0/R1/R2/R3 exemplo (fake) + move-selection + state-reconstruction + full-game
- [x] paired openings suite (cores invertidas) com pair IDs
- [x] baseline random-legal + scripted + UCI opponent (fake engine nos exemplos)
- [x] relatório capability/cost por condição (nunca mistura classes de assistência)
- [x] preregistration/experiment-card ligado ao manifest (skill design-research-experiment)
- [x] docs: como executar suite fake offline, o que o resultado mede e não mede

Exit M6:
- [x] suite fake completa roda offline de ponta a ponta
- [x] relatório Markdown + JSON + Parquet gerados
- [x] todos os gates M0–M5 verdes

## P-final — Definition of Done v0.1 (§31 do design, 20 itens)

- [x] 1. instalação limpa do CLI
- [x] 2. `zugzwang doctor` valida workspace/DB/plugins/engine opcional
- [x] 3. manifesto R0–R3 valida e planeja
- [x] 4. fake provider executa tudo offline
- [x] 5. contract smoke: adapter OpenAI-compatible local (sem rede); pydantic-ai mock
- [x] 6. MoveSelection, FullGame, StateReconstruction funcionam
- [x] 7. random legal + UCI opponent (fake engine) funcionam
- [x] 8. interrupção em qualquer step retoma sem duplicar ação commitada
- [x] 9. toda chamada e retry aparece no event stream
- [x] 10. nenhuma ação ilegal aplicada (perft/property/fuzz)
- [x] 11. assistência declarada vs efetiva comparadas
- [x] 12. avaliação Stockfish pós-hoc gera métricas versionadas (fake UCI no CI; binário real opcional do usuário)
- [x] 13. run finaliza em bundle com checksums
- [x] 14. bundle importado e reavaliado offline
- [x] 15. Parquet consultável via DuckDB
- [x] 16. CLI com output JSON estável
- [x] 17. CI padrão sem rede nem secrets
- [x] 18. migrations e compatibility fixtures passam
- [x] 19. SBOM e lockfile produzidos
- [x] 20. documentação explica o que o resultado mede e não mede
- [x] Completion report YAML conforme AGENTS.md

---

## Stack real (pós-DoD, autorizado por Mestre Mael 2026-08-16)

- [x] GATE-003 ratificado: captura integral local privada; export público bloqueado (GATE-005)
- [x] GATE-006 ratificado: binário oficial SF 18 (sse41-popcnt, sha256 f89b3b35...) em ~/.local/bin/stockfish; sem redistribuição
- [x] plugin `provider-opencode`: servidor headless opencode via session/message HTTP; 1 call = 1 session isolada; usage real (source=provider); erros tipados
- [x] backend factory por manifest: backend_config {base_url, provider_id, timeout_seconds}
- [x] experiments/real-opencode-move-selection.yaml (opencode-go/deepseek-v4-flash — LLM principal dos testes reais)
- [x] .env local com OPENCODE_GO_API_KEY (gitignored) + .env.example sem segredo
- [x] adapter sem model na criação de sessão (opencode-go rejeita com 400); modelo vai só no message
- [x] tests/e2e/test_real_stack.py: 3 e2e verdes (deepseek-v4-flash pago via OpenCode Go + SF18 real)
- [x] evidência: lance real "e2e4"; attempt completed, 3988 ms, usage {input 98, output 5, source provider}
- [x] gates offline continuam verdes (151 testes + pyright + ruff + foundation strict)

## Research Suite 0.1 (ZGW-0073..0076, 2026-08-16)

- [x] ZGW-0073 multimodal: ImagePart (CAS+sha256+renderer metadata), renderer Pillow byte-determinístico (tema/orientação/coordenadas/tamanho), observation.image + fen_override + modality_authority, image_conflict manifest (delta_squares), lowering opencode FilePart data-URL e openai-compatible image_url, preflight MULTIMODAL_IMAGE sem fallback silencioso (ADR-046); spike real mimo-v2.5 lê tabuleiro
- [x] ZGW-0074 knowledge: KClass K0-K7 (ADR-047 emenda ADR-034), KnowledgePacket estático (schema+loader+auditoria de leakage+hash na condition identity), injeção no prompt com K impact por episódio; packets SKILL-001 S2-S8 com token-matching S4≈S5≈S6
- [x] ZGW-0075 grounding: chess.reason_then_ground G4 (2 fases, análise sem legal set, candidatos no trace), G3 SAN legal set + resolve UCI, protocol.prompt (persona/few-shot) no hash de protocolo, effective H/K por episódio (H3/K0 no G4)
- [x] ZGW-0076 suite: corpus 10 posições congeladas (sha256), 14 manifests gerados deterministicamente, experiment card + preregistration, decision packet GATE-011, piloto e2e real (6 condições, 1 posição Najdorf) com Stockfish 18 pós-hoc
- [x] gates: 190 offline + 8 e2e verdes; ruff/pyright/foundation strict verdes

## Estado da sessão

- Início: 2026-08-16
- Gates ratificados: GATE-001, GATE-002, GATE-004
- Milestone atual: COMPLETO (v0.1)
- P-final concluído: 151 testes offline + 1 skip (e2e opt-in); todos os gates verdes; DoD 20/20
- M5 concluído: 147+ testes; redaction/secret-refs/tool broker/upcasters/SBOM CycloneDX/doctor completo/compat fixtures/tamper rejection
- M6 concluído: suite fake R0-R3 (4 condições), paired openings 2x2, reconstruction com scoring; docs V0_1_FAKE_SUITE.md
- M4 concluído: 133 testes verdes; bundle roundtrip + detecção de tampering; parquet/duckdb; GC; cache de engine comprovado; R3 end-to-end
- M3 concluído: 124 testes verdes; contract suite em 3 backends offline; R1 opaque-index e R2 repair (2 attempts registrados) end-to-end
- M2 concluído: 30 testes unitários de xadrez + 3 integração verdes; perft Kiwipete/CPW depth 1-2; full-game vs random-legal com 8 plies; ação ilegal nunca aplicada (teste dedicado)
- M1 concluído: 81 testes offline, fault suite verde (5), resume sem duplicação comprovado, CLI runs/list/show/resume/cancel/db funcionais
- M0 concluído: 69 testes offline verdes, pyright strict 0 erros, foundation strict PASS 9

## ZGW-0079 evidence and model-only search

- [x] ObservationArtifact and DecisionTraceArtifact are stored per model step
- [x] provider wire request/response and reasoning telemetry have direct attempt references
- [x] binary versus enumerated legality exposure is explicit and audited
- [x] EvaluationRun separates post-hoc generations
- [x] SearchWorkspace persists immutable nodes, edges and endogenous retrievals
- [x] R6-BatchedTree completes with the same model as candidate generator and judge
- [x] real proxy, Stockfish opponent and post-hoc evaluation were exercised without a fake model
