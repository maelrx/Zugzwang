# Requisitos funcionais

**Baseline:** FR-001 a FR-055 do design greenfield, estendidos nesta edição.

### 4.1 Workspace, configuração e descoberta

| ID | Requisito | Aceitação resumida |
|---|---|---|
| FR-001 | Inicializar workspace local | `zgw init` cria layout e config sem servidor |
| FR-002 | Validar manifesto | erro aponta caminho, valor, schema e sugestão |
| FR-003 | Exportar JSON Schema | schema versionado para tooling externo |
| FR-004 | Resolver manifesto | defaults, plugins, capabilities e preços ficam congelados |
| FR-005 | Planejar sem executar | mostra episódios, chamadas previstas, budget e incompatibilidades |
| FR-006 | Expandir matrizes | `product` e `zip` determinísticos, com IDs estáveis por condição |
| FR-007 | Descobrir plugins | entry points locais, sem consulta de rede |
| FR-008 | Inspecionar capabilities | provider/model/tool/evaluator exibem suporte declarado |

### 4.2 Execução

| ID | Requisito | Aceitação resumida |
|---|---|---|
| FR-009 | Criar run imutável | `ResolvedManifest` não muda após início |
| FR-010 | Executar episódios concorrentes | limites por provider e budget são respeitados |
| FR-011 | Executar R0–R3 | cada estratégia produz trace explícito |
| FR-012 | Chamar modelos por contrato comum | request/response normalizados e raw preservado quando disponível |
| FR-013 | Executar tools tipadas | input validado, output versionado, side effect declarado |
| FR-014 | Aplicar ação somente pelo environment | model/tool não muta estado canônico diretamente |
| FR-015 | Validar parsing e legalidade | parse error e illegal action são categorias distintas |
| FR-016 | Registrar toda tentativa | transporte, throttling, parse e retry sem sobrescrita |
| FR-017 | Impor budgets | calls, tokens, USD, wall time e retries possuem limites |
| FR-018 | Impor rate limits | semáforos/token buckets por backend/modelo |
| FR-019 | Cancelar/interromper | `Ctrl-C` gera checkpoint consistente |
| FR-020 | Retomar | steps já commitados não são repetidos |
| FR-021 | Finalizar idempotentemente | repetir finalização não duplica métricas ou artefatos |

### 4.3 Xadrez

| ID | Requisito | Aceitação resumida |
|---|---|---|
| FR-022 | Manter estado integral | posição, lado, roque, en passant, contadores e repetição |
| FR-023 | Codificar observações | FEN, ASCII, histórico e combinações configuráveis |
| FR-024 | Codificar ações | UCI canônico; SAN apenas como codec de interface |
| FR-025 | Enumerar ações legais | conjunto e hash reproduzíveis |
| FR-026 | Suportar ações opacas | índices sem leakage semântico opcional |
| FR-027 | Partidas completas | termination e resultado formalmente verificados |
| FR-028 | Move selection | posição fixa com candidatos livres ou grounded |
| FR-029 | State reconstruction | comparar estado previsto ao canônico |
| FR-030 | Aberturas pareadas | mesma abertura com cores invertidas |
| FR-031 | Oponentes plugáveis | random legal, policy, script/replay e UCI engine |
| FR-032 | Exportar PGN estrito | partida principal reproduzível, sem exigir parser rico |

### 4.4 Persistência, artefatos e replay

| ID | Requisito | Aceitação resumida |
|---|---|---|
| FR-033 | Persistir estado operacional | SQLite local com migrations |
| FR-034 | Registrar eventos append-only | envelope versionado e sequência monotônica por agregado |
| FR-035 | Armazenar blobs por conteúdo | SHA-256, escrita atômica e deduplicação |
| FR-036 | Produzir run bundle | manifesto, eventos, objetos, métricas e checksums |
| FR-037 | Importar bundle | valida schema e checksums antes de registrar |
| FR-038 | Replay offline | parsing, transição e avaliação podem ser refeitos sem provider |
| FR-039 | Garbage collection segura | remove apenas objetos não referenciados após grace period |
| FR-040 | Doctor | detecta dangling refs, órfãos, migrations e engines inválidos |

### 4.5 Avaliação e relatórios

| ID | Requisito | Aceitação resumida |
|---|---|---|
| FR-041 | Avaliação pós-hoc | engine não entra no decision loop por acidente |
| FR-042 | Métrica com proveniência | definição, versão, source, config e scope |
| FR-043 | Métricas operacionais | latency, calls, tokens, retries, failures, custo |
| FR-044 | Métricas enxadrísticas | outcome, legal rate, CPL/ACPL, blunders e fase |
| FR-045 | Estatística pareada | bootstrap por pares/openings quando aplicável |
| FR-046 | Consultar via DuckDB | Parquet sem depender do SQLite operacional |
| FR-047 | Saída humana e machine-readable | terminal/Markdown e JSON/JSONL/Parquet |
| FR-048 | Separar classes de sistema | model-only, grounded e engine-assisted nunca agregados juntos |

### 4.6 Segurança e governança

| ID | Requisito | Aceitação resumida |
|---|---|---|
| FR-049 | Secret references | segredos não entram no manifesto resolvido ou bundle |
| FR-050 | Redaction | logs e raw artifacts passam por política explícita |
| FR-051 | Tool allowlist | nenhuma execução arbitrária pelo modelo; providers first-party model-only, recibos externos rejeitados com evidência, sem commit/retry; provider sem isolamento verificável bloqueado (ADR-063) |
| FR-052 | Auditoria de assistência | classe declarada, observada e violações registradas |
| FR-053 | Auditoria de plugins | versão, distribuição, licença e hash do ambiente |
| FR-054 | Base URL confiável | endpoints customizados exigem opt-in explícito |
| FR-055 | Engine sandbox | timeout, env mínimo e resource limits quando suportados |

---


## Extensões desta edição

### Multimodalidade e conhecimento

| ID | Requisito | Aceitação resumida |
|---|---|---|
| FR-056 | Content parts tipados | texto, estado estruturado, imagem e tool result atravessam contrato canônico |
| FR-057 | Artifact visual reproduzível | bytes, hash, MIME, dimensões, renderer, orientação e source state registrados |
| FR-058 | Capability multimodal | ausência de image input falha ou pula condição explicitamente |
| FR-059 | Conflito de fontes | observation registra autoridade e conflito intencional |
| FR-060 | Knowledge packets | packet estático possui schema, versão, provenance, licença e K class |
| FR-061 | Injeção token-controlada | strategy registra packet e token overhead |
| FR-062 | Dual assistance | H e K declarados, efetivos e auditados separadamente |
| FR-063 | Experiment cards | cada suite pública possui pergunta, hipótese, outcomes e promotion gate |
| FR-064 | Paired condition execution | planner preserva position-family e condition pairing |
| FR-065 | Retention policy | cada artifact class declara full/redacted/encrypted/hash-only/omitted |
| FR-066 | Authority probe | multimodal tasks podem avaliar qual fonte governou a resposta |
| FR-067 | Schema fixtures | exemplos válidos e inválidos existem para cada contrato público |

### Governança de decisão

| ID | Requisito | Aceitação resumida |
|---|---|---|
| FR-068 | Human gates | gates human-owned com `status: pending` bloqueiam o milestone/release correspondente |
| FR-069 | ADR traceability | mudança de contrato aponta para ADR e requisitos afetados |
| FR-070 | Source provenance | claims científicos distinguem material fornecido, pesquisa externa e inferência própria |
