# Estado operacional e fila de integração

Atualização: 2026-09-05, ZGW-0085. Este mapa distingue a main, mudanças em revisão e trabalho local. O estado atual de cada PR no GitHub prevalece sobre esta fotografia.

## Base para trabalhos novos

O kernel Python e uv.lock já existem. M0-M6 possuem entregas implementadas e testes; os critérios de reprodução independente e validação científica ainda têm pendências. Consultar o [roadmap](../roadmap/ROADMAP.md) e os [gates](../decisions/DECISIONS.yaml).

Comece trabalho independente em branch/worktree da main atualizada. Trabalho que dependa da pilha experimental deve declarar o PR-base. Não trocar a venv ou os arquivos de outro agente.

## Pilha existente

| PR | Branch | Base | Situação |
|---|---|---|---|
| [#9](https://github.com/maelrx/Zugzwang/pull/9) | codex/zgw-foundation | main | Bloqueado: typing isolado, timeout e métricas legadas, issue #13 |
| [#10](https://github.com/maelrx/Zugzwang/pull/10) | codex/zgw-agentic-strategies | codex/zgw-foundation | Depende de #9; validar docs e escopo no próprio head |
| [#11](https://github.com/maelrx/Zugzwang/pull/11) | codex/zgw-validation-evidence | codex/zgw-agentic-strategies | CI observado verde; depende da pilha e da revisão de publicação de dados |
| [#12](https://github.com/maelrx/Zugzwang/pull/12) | codex/zgw-single-agent-tree-experiments | codex/zgw-validation-evidence | Bloqueado pelos contratos das ablações, issue #14 |

Contagens de testes dos corpos antigos foram obtidas no branch integrado, não certificam os heads anteriores isolados. MERGEABLE significa ausência de conflito Git, não correção científica.

## Fontes locais agora em PRs separados

| PR | Branch | Base | Revisão pendente |
|---|---|---|---|
| [#17](https://github.com/maelrx/Zugzwang/pull/17) | codex/zgw-viewer-next-review | codex/zgw-validation-evidence | Viewer/engine visual, lint, escopo e dados; fixture vazia no lugar do snapshot |
| [#18](https://github.com/maelrx/Zugzwang/pull/18) | codex/zgw-overnight-experiments-review | codex/zgw-single-agent-tree-experiments | Manifestos históricos e log corrigido por aviso explícito; depende de #14/ZGW-0084 |
| [#19](https://github.com/maelrx/Zugzwang/pull/19) | codex/zgw-local-overlays-review | codex/zgw-single-agent-tree-experiments | Alternativas locais de migration/builder/viewer e replicações; reconciliar antes de integrar |

Esses PRs são drafts. Preservam fontes selecionadas do commit overnight `18c98ae` ou dos overlays locais; não enviam o histórico local completo contendo snapshots privados. O histórico original permanece localmente preservado.

## Trabalho local preservado

- `overnight/h3-runs`, worktree `Zugzwang-night`: ZGW-0083 e viewer, com correções ZGW-0084 em andamento pelo Hermes. Não rebasear nem incorporar arquivos ainda mudando.
- Commit local da main `3085f3b`: exclusões de graphify e snapshots incorporadas à organização documental.
- Migrações 0003/0004/0005 soltas na main são idênticas às da fundação. Outros overlays, manifests de replicação e fontes de viewer foram preservados no #19 para reconciliação; não usar `git add .` na main.
- Links locais de `.agents/skills/` são configuração do host. Skills canônicas também existem versionadas, embora possam estar ocultas pelo sparse checkout. Não publicar symlinks de caminhos absolutos nem ignorar todo o catálogo canônico.
- Bancos, CAS e snapshots `viewer/data*` são evidência privada. Não são publicados ou apagados pela organização.

## Pendências

1. [#13: fundação](https://github.com/maelrx/Zugzwang/issues/13): PR autocontido, timeout honesto, métricas legadas e assistência do oponente.
2. [#14: ciência](https://github.com/maelrx/Zugzwang/issues/14): largura, exposição antes da seleção, memória, corpus e confundimentos.
3. [#15: reprodução](https://github.com/maelrx/Zugzwang/issues/15): bundle independente, asserções, validator e e2e opt-in.

Relaunch, aumento de orçamento e mudança de regime são decisões separadas da organização Git. Comentários de revisão não autorizam gastos nem ratificam gates.

## Regra de merge

Validar head, dependências e critérios da issue. Não mergear em branch-base apenas para reduzir a fila. Corrigir bloqueios no menor PR responsável. Preservar branches de trabalho não integradas.
