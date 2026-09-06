# Handoff ZGW-0085

Organização autorizada por Mestre Mael em 2026-09-05. Clone e venv isolados; nenhuma operação em bancos ou execução de modelos.

## Resultado

Entradas documentais descrevem o kernel implementado e as decisões efetivamente aceitas. O [mapa operacional](REPOSITORY_STATUS.md) relaciona branches, PRs e issues #13/#14/#15. Exclusões evitam inclusão acidental de snapshots novos. Links de skills do host são preservados localmente; skills canônicas versionadas continuam rastreadas.

## Integração e evidência

O PR documental não corrige nem aprova os mecanismos experimentais em revisão. Quality gates rodam no lockfile existente e ambiente isolado; comandos, resultados e head verificado são registrados na conversa do PR antes do merge.

## Preservação e próximos trabalhos

Alterações locais foram copiadas para evidência privada. Nenhuma branch não mergeada, worktree ativa, resultado falho ou artefato privado foi removido. ZGW-0084 permanece com Hermes. Resolver #13 antes de avançar na pilha; #14 exige contratos/amendments; #15 exige reprodução independente. O GitHub registra a situação atual dos PRs.

## Checks do PR documental

- Lockfile instalado em clone/venv isolados.
- Pytest offline: 190 passed, 1 skipped, 6 deselected em 13.58 s.
- Ruff: passou; format: 354 files already formatted.
- Pyright: 0 errors, 0 warnings com `uv run --no-sync pyright`.
- Foundation strict: PASS 9, WARN 0, ERROR 0.
- CI remoto inicial do PR [#16](https://github.com/maelrx/Zugzwang/pull/16): Python 3.13/3.14 e validator verdes; e2e excluído.
- Novas fontes em drafts #17/#18/#19: diff e sintaxe conferidos; build/QA visual e execução real não repetidos.

Os PRs #9-#12 têm comentários de bloqueio e descrições atualizadas. O commit final documental deve ter seus próprios checks remotos verdes antes de merge.

## Encerramento da fila (2026-09-06)

A fila foi concluída conforme o plano: #13 resolvido no #9 (merge `a18a4a1`), #10 trazido à main pelo #20 (`cc86bcb`), #11 (`fd33f49`) com `viewer/data.js` desrastreado (GATE-005), #12 (`79ac81a`) com correções da #14 e corpus 1.1.0, #21 (`ccec405`) com a reprodução por bundle da #15, e preservações #18/#19 e viewer-next #17 integradas por último. Issues #13/#14/#15 fechadas com evidência; detalhes em [REPOSITORY_STATUS.md](REPOSITORY_STATUS.md).

Gates humanos e ZGW-0084 permanecem como registrados; nenhum gate foi ratificado por esta organização.
