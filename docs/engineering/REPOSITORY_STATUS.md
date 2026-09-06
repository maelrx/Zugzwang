# Estado operacional e fila de integração

Atualização: 2026-09-06, ZGW-0085 (encerramento da fila). A fila de integração documentada em 2026-09-05 foi concluída: todos os PRs da pilha foram corrigidos no próprio head, validados e mergeados na main. O estado atual de cada PR no GitHub prevalece sobre esta fotografia.

## Base para trabalhos novos

O kernel Python e uv.lock existem. M0-M6 possuem entregas implementadas e testes; os critérios de reprodução independente e validação científica ainda têm pendências. Consultar o [roadmap](../roadmap/ROADMAP.md) e os [gates](../decisions/DECISIONS.yaml).

Comece trabalho independente em branch/worktree da main atualizada (`4bbe579` ou posterior). Trabalho que dependa da pilha experimental já encontra as strategies R5/R7, a bateria single-agent H1–H5 e o corpus 1.1.0 na main. Não trocar a venv ou os arquivos de outro agente.

## Fila de integração — concluída

| PR | Conteúdo | Resultado |
|---|---|---|
| [#9](https://github.com/maelrx/Zugzwang/pull/9) | Fundação auditável (provider, engine, search R6) + correções da issue #13 | Merged (`a18a4a1`) |
| [#10](https://github.com/maelrx/Zugzwang/pull/10) | Estratégias agentic R5/R7 + wiring no coordinator | Merged na fundação; trazido à main por [#20](https://github.com/maelrx/Zugzwang/pull/20) (`cc86bcb`) |
| [#11](https://github.com/maelrx/Zugzwang/pull/11) | Relatórios, scripts e viewer; `viewer/data.js` desrastreado (GATE-005) | Merged (`fd33f49`) |
| [#12](https://github.com/maelrx/Zugzwang/pull/12) | Bateria single-agent H1–H5 + correções da issue #14 + corpus 1.1.0 | Merged (`79ac81a`) |
| [#21](https://github.com/maelrx/Zugzwang/pull/21) | Reprodução por bundle, asserções honestas, CI/validator (issue #15) | Merged (`ccec405`) |
| [#18](https://github.com/maelrx/Zugzwang/pull/18) | Preservação dos manifestos overnight | Merged |
| [#19](https://github.com/maelrx/Zugzwang/pull/19) | Preservação dos overlays locais | Merged |
| [#17](https://github.com/maelrx/Zugzwang/pull/17) | Viewer-next (Vite/React/TS) separado de dados privados | Merged (`4bbe579`) |

Issues [#13](https://github.com/maelrx/Zugzwang/issues/13), [#14](https://github.com/maelrx/Zugzwang/issues/14) e [#15](https://github.com/maelrx/Zugzwang/issues/15) fechadas com evidência nos comentários.

## Viewer oficial (ZGW-0102, 2026-09-06)

A experiência "Research workspace" do viewer-next (biblioteca de execuções, replay, análise, evidências, comparação) é o viewer oficial, com sistema de aparência (temas/texturas/escala de fonte) e snapshot ao vivo via `viewer-next/scripts/regen-snapshot.sh`. A linhagem anterior de camadas L0/L1/L2 (ZGW-0097/CB-WO-10) foi removida da UI; dados cognitivos permanecem no banco e na análise oficial. Branch `codex/zgw-viewer-appearance`.

## Notas de integração

- A divisão #9/#10 foi corrigida: a fundação falha fechada nas strategies R5/R7 e o PR que as introduz faz o wiring (`durable_coordinator.py`).
- `viewer/data.js` não é versionado; fixture vazia é gerada localmente e clones novos usam `scripts/build_readonly_viewer.py`. Snapshots de runs reais permanecem evidência privada (GATE-005 pendente).
- \`bundle.json\` ganhou \`condition_id\` opcional (aditivo, retrocompatível); \`rebuild_projections\` reconstrói projeções a partir do event stream do bundle.
- Corpus: `datasets/positions_v1` (1.0.0) permanece congelado como evidência; execuções novas usam `datasets/positions_v1_1` (1.1.0, P01/P09 corrigidos). Emenda 001 da suite 0.1 registrada antes de qualquer execução paga.

## Trabalho local preservado

- `overnight/h3-runs`, worktree `Zugzwang-night`: ZGW-0083 e correções ZGW-0084 do Hermes permanecem locais, sem push, por diretiva da missão. A versão de trabalho de `analyze_deep.py` e das migrations 0006 continua lá; a cópia em PR é snapshot para revisão. Não rebasear nem incorporar arquivos ainda mudando.
- Links locais de `.agents/skills/` são configuração do host. Não publicar symlinks de caminhos absolutos.
- Bancos, CAS e snapshots `viewer/data*` são evidência privada. Não são publicados ou apagados.

## Pendências

1. ZGW-0084 (Hermes, worktree night): fechamento formal das correções de mecanismo e da condição `a` da triple clean.
2. GATE-005/007/008/009/010/011/012 seguem pendentes em `DECISIONS.yaml`; execução paga da suite 0.1 exige GATE-011.
3. Reprodução independente em máquina limpa e validação científica completa da suite 0.1 (critérios de saída de milestone).
4. Adjudicação retroativa das partidas overnight (n=1, exploratórias) e multi-seed pareada H3×H2 como pré-requisito de claims.

Relaunch, aumento de orçamento e mudança de regime são decisões separadas. Comentários de revisão não autorizam gastos nem ratificam gates.

## Regra de merge

Validar head, dependências e critérios da issue. Corrigir bloqueios no menor PR responsável. Preservar branches de trabalho não integradas e worktrees ativas.
