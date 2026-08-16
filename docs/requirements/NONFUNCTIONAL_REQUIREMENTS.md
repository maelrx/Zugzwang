# Requisitos não funcionais

| ID | Propriedade | Meta/critério |
|---|---|---|
| NFR-001 | Correção formal | nenhuma ação ilegal é aplicada ao ambiente |
| NFR-002 | Auditabilidade | toda chamada externa possui request, attempts, response/failure e usage |
| NFR-003 | Crash consistency | não pode existir referência commitada para artefato ausente |
| NFR-004 | Retomabilidade | run interrompido retoma do primeiro step incompleto |
| NFR-005 | Reprodutibilidade honesta | níveis de replay/rerun/determinismo são declarados |
| NFR-006 | Extensibilidade | provider/evaluator/environment novo não exige editar o kernel |
| NFR-007 | Core independente | importar `zugzwang.core` não carrega provider, DB, chess, CLI ou engine |
| NFR-008 | Local-first | nenhuma infraestrutura externa além do provider escolhido |
| NFR-009 | Portabilidade | Linux, macOS e Windows onde dependências nativas possuírem wheel |
| NFR-010 | Bounded concurrency | memória e chamadas crescem com limite configurado, não com total de episódios |
| NFR-011 | Backpressure | fila de persistência tem limite e desacelera producers |
| NFR-012 | Sem comportamento oculto | fallback, retry e coercion são desativados ou registrados |
| NFR-013 | Segurança padrão | sem shell, filesystem amplo ou execução de código por modelo |
| NFR-014 | Observabilidade local | JSON logs e eventos bastam sem SaaS proprietário |
| NFR-015 | CI offline | suíte padrão não chama providers nem baixa engine |
| NFR-016 | Compatibilidade de schema | bundle antigo possui leitor/migrator explícito |
| NFR-017 | Qualidade estática | typing estrito, lint, arquitetura e testes no CI |
| NFR-018 | Migração de storage | repositories não expõem SQLAlchemy ao domínio |
| NFR-019 | Idempotência | finalize/evaluate/import podem ser repetidos com mesmo resultado lógico |
| NFR-020 | Performance suficiente | overhead interno não domina chamadas de rede/engine; otimização guiada por profiles |

Não se deve publicar um SLA artificial como “p95 < 20 ms” antes de workloads reais. O critério correto no v0.1 é que o overhead do kernel seja mensurado e permaneça materialmente menor que inferência e avaliação, com benchmarks versionados.

---


## Extensões desta edição

| ID | Propriedade | Meta/critério |
|---|---|---|
| NFR-021 | Multimodal integrity | exact bytes enviados ao provider possuem hash e lowering auditável |
| NFR-022 | Knowledge attribution | ganho não pode ser agregado sem K class e packet identity |
| NFR-023 | Provider defensiveness | novos message parts/optional fields não quebram silenciosamente o adapter |
| NFR-024 | SQLite safety | doctor recusa runtime WAL vulnerável sem override explícito de desenvolvimento |
| NFR-025 | Documentation as code | links, schemas, ADR IDs e skill frontmatter validados em CI |
| NFR-026 | Decision safety | agente não ratifica gate reservado ao operador humano |
| NFR-027 | Data minimization | retenção full é configurável e secrets/PII são redacted |
| NFR-028 | Scientific comparability | reports não agregam conditions com fingerprints incompatíveis |
| NFR-029 | Renderer determinism | mesma state/render config produz mesmo artifact em supported platform |
| NFR-030 | Import hostility | bundle importado é validado, size-limited e tratado como não confiável |
