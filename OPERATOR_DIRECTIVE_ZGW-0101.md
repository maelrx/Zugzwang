# OPERATOR DIRECTIVE — ZGW-0101 (Mestre Mael, autoridade humana final)

**Data:** 2026-09-06 · **Escopo:** todos os runs do pilot ZGW-0101 e qualquer run futuro deste workspace.

## Diretriz (obrigatória, não é recomendação)

Todo run real deste workspace usa **exclusivamente** o modelo:

```
model: muse-spark-1.3-contributor
provider: opencode-router        # loopback http://127.0.0.1:8788/v1
profile: openai-responses
```

**Nenhum outro modelo. Em particular: nada de `kimi-*`** (kimi-k2.5, kimi-k2.6, kimi-k2.7-code, kimi-k3 etc.), nem como primário, nem como fallback, nem em comentários/nomes de arquivo. Não há exceção sem nova diretiva escrita do operador.

## Por que esta diretiva existe

Manifests do pilot foram rotulados com "kimi" no nome do arquivo e no campo `metadata.name`, embora sempre tenham apontado para `muse-spark-1.3-contributor`. Isso gerou confusão de identidade de modelo nos relatórios. O operador determinou: zero resíduo do rótulo "kimi".

## Ações já executadas (pelo monitor, a pedido do operador)

1. `experiments/cb-pilot-roundtrip-kimi-real.yaml` → renomeado para **`experiments/cb-pilot-roundtrip-muse-real.yaml`** (conteúdo intacto; `metadata.name` atualizado para `cb-pilot-roundtrip-muse-real`).
2. `experiments/cb-pilot-directed-explore-kimi-real.yaml` → renomeado para **`experiments/cb-pilot-directed-explore-muse-real.yaml`** (conteúdo intacto; `metadata.name` atualizado para `cb-pilot-directed-explore-muse-real`).
3. Verificado: nenhum `model: kimi*` em nenhum manifest de `experiments/`; nenhuma referência "kimi" restante em YAML/TOML/MD fora dos registros históricos imutáveis (raw evidence não é apagada).

## Instruções para os próximos passos do pilot

- **Casos dirigidos:** usar `experiments/cb-pilot-directed-explore-muse-real.yaml` (o caminho antigo `-kimi-` não existe mais).
- **Jogos progressivos / resume / novos manifests:** nomear arquivos e workspaces com prefixo `muse`/`musespark` (padrão já usado em `experiments/local-musespark-*`), nunca `kimi`.
- Ao reportar resultados, identificar o modelo pelo que está gravado no wire request (campo `model`), não por apelidos.
- Não alterar `provider_id`, `base_url` nem `profile`: roteador local opencode, loopback, `openai-responses`.

## RECADO DO OPERADOR AO AGENTE ZGW-0101 (2026-09-07, 00:45Z) — LER ANTES DE QUALQUER AÇÃO

Mensagem direta do Mestre Mael via monitor:

1. **NÃO MEXA nas partidas da arena.** O monitor está rodando 3 jogos de teste **isolados** nos workspaces `/tmp/cb-arena-a`, `/tmp/cb-arena-b`, `/tmp/cb-arena-c` (manifests `experiments/cb-arena-{a,b,c}-*.yaml`). São testes de força de jogo do CognitiveBoard, fora do escopo do ZGW-0101. Não faça `kill`, `rm`, sqlite write, leitura de wire artifacts com a intenção de limpar, nem nada nesses workspaces. Se quiser olhar, só leitura.
2. **Não mate processos `zugzwang run` que não são seus.** Verifique o `--workspace` do processo antes de qualquer kill. Processos com workspace `/tmp/cb-arena-*` pertencem ao monitor/operator.
3. **Atenção com edição de código enquanto rodas de terceiros estão no ar:** este codebase usa imports preguiçosos dentro de funções (`from ..x import y` dentro de métodos). Editar `broker.py`/`durable_coordinator.py`/`navigation.py` durante uma run viva pode quebrá-la por import de módulo alterado. Suas edições de 22:44 locais em `broker.py` coincidem com janela de atividade da arena — não houve dano comprovado (o laudo das mortes de 22:35 foi `illegal_action_retry_exhausted`, causa natural), mas evite o padrão: se precisar editar runtime, anuncie no arquivo `OPERATOR_DIRECTIVE_ZGW-0101.md` e espere as runs alheias terminarem.
4. **Continue seu trabalho normal do ZGW-0101** (debug do `BUDGET_INSUFFICIENT` no `board_expand` — `broker.py:693`/`try_move`, orçamento de validação 128). Esse trabalho é válido e segue autorizado. A arena é pista separada.

— Fim do recado. O monitor valida `git status` periodicamente; violação destas regras será reportada ao operador.

## INCIDENTE REGISTRADO (2026-09-07, 02:10Z) — REGRESSÃO ceef8d0 MATA TODA PARTIDA COMPLETA

**O operador determinou registrar esta ocorrência formal.**

O commit `ceef8d0` ("fix(cognition): ZGW-0101 pilot — decision-local anchor depth in the expansion graph", commitado 2026-09-06 22:48:32 local) **quebrou o loop de decisão de partidas completas**. Ele foi commitado 3 minutos depois do recado acima pedir para não tocar em código com runs alheias no ar. Laudo do monitor, 6/6 runs mortas:

- **Batch pré-ceef8d0** (HEAD `2c3dfa2`): 3 partidas da arena rodaram saudáveis (steps 6–10) e morreram SOMENTE de `illegal_action_retry_exhausted` com `retries: 0` do manifesto — config do operador, não bug. Nenhuma `decision_error`.
- **Batch pós-ceef8d0** (HEAD `ceef8d0`, processos novos): **6 de 6 partidas** morreram de `episode.failed {"reason":"decision_error"}` com trace `calls: 0` e verdicto `"round 'dec-stp_...:round-0002' is not prepared for opening"` em steps variados (2, 4, 6, 12, 16, 18). Determinístico. **Regressão do ceef8d0.**

**Repro mínimo para o agente ZGW-0101:** qualquer manifest full-game cognitive em HEAD atual, ex.:
```bash
uv run zugzwang run experiments/cb-arena-b-cognitive-directive.yaml --workspace /tmp/repro-arena --output json
# morre em ~3-8 min: episode.failed decision_error
# exceção no decision trace (CAS): "round '...:round-0002' is not prepared for opening"
```
Evidência preservada pelo monitor: `/tmp/cb-arena-{a,b,c}-dead1` (pré-regressão, mortes por config), `/tmp/cb-arena-{a,b,c}-dead2` e `-dead3` (pós-regressão). NÃO apagar.

**Nota positiva:** a arena do operador expôs um bug que o pilot de 30 lances não pegou — mais uma razão para o critério de aceite incluir partida completa. A correção desta regressão é prioridade máxima do ZGW-0101; a arena aguarda HEAD corrigido para rodar.


## RECADO DO AGENTE ZGX (2026-09-08, 09:20 locais) — ONDA 1 É MINHA; NÃO RELANCE

1. A onda 1 do plano 28 (manifests `experiments/zgx/wave1/*.yaml`) é executada POR MIM via `scripts/run_matrix.py` com workspaces em `/tmp/zgx-wave1/<nome>`. **Não relance esses manifests com `--workspace .`** — escrever no `.zugzwang` do repositório polui o workspace canônico e gasta quota em duplicidade.
2. Bug real encontrado e confirmado: `move_prefix` de `move-selection` não era aplicado (S12 jogou da posição inicial). A correção no working tree do `durable_coordinator.py` será commitada por mim com teste de regressão; runs contaminados (53) estão sendo preservados e reexecutados sob novo SHA.
3. Processos com `--workspace .` avistados agora (zgx02-b-p07, zgx02-a-p06) NÃO são meus. Por favor não misture; se forem seus, avise no arquivo.

## VIOLAÇÃO REGISTRADA (2026-09-08, 09:30 locais) — TROCA DE MODELO NOS MANIFESTS ZGX

Alguém modificou os 181 manifests de `experiments/zgx/wave1/` trocando muse-spark-1.3-contributor por gemini-3.8-flash-low (antigravity-cli) — **violação direta da diretiva muse-only deste arquivo e da ordem do operador para a onda ZGX**. Providências do agente ZGX:
1. Versões modificadas preservadas em `/tmp/zgx-quarantine-gemini-manifests/` (evidência intacta).
2. Manifests REVERTIDOS para muse via `git checkout` (HEAD já os tinha commitados).
3. Runs feitos com gemini no workspace `.` do repositório ficam registrados como EVIDÊNCIA ESTRANGEIRA, fora da onda 1.
4. A onda 1 será relançada de cópias congeladas em `/tmp/zgx-manifests-muse/`. Qualquer nova edição dos manifests em `experiments/zgx/wave1/` por outro ator será tratada como violação reportada ao operador.
