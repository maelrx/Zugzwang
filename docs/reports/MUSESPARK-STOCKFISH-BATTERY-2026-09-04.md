# Bateria MuseSpark 1.3 contra Stockfish

## Resumo

Foram executadas dez partidas, uma por variante, com o MuseSpark 1.3 Free de
brancas e Stockfish de pretas. Todas chegaram a xeque-mate, com vitória do
Stockfish. O limite de meios-lances ficou desativado (`max_plies: null`).

O alvo configurado foi Elo 1000. O binário local só aceita Elo UCI nativo a
partir de 1320, então o perfil usado foi documentado como aproximado: UCI Elo
1320 com `Skill Level 0`. Isso não equivale a um rating calibrado de 1000.

As métricas abaixo usam o evaluator `evaluator.stockfish.precise` 0.3.0. Para
cada lance do modelo, o evaluator analisa a posição FEN antes do lance, a
posição depois do lance e calcula `CPL = max(score_antes - score_depois, 0)` na
perspectiva do modelo. O primeiro score UCI é o último `info` MultiPV 1
recebido. O histórico não é reaplicado depois do FEN.

## Resultados finais

| variante | alteração | plies | CPL médio | mediana | pior CPL | blunders | erros | imprecisões | acordo SF | rejeições ilegais | chamadas | tokens in/out |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | FEN + últimos 6 UCI | 58 | 634,7 | 88 | 8.397 | 10 | 4 | 2 | 24,1% | 10 | 39 | 6.585 / 37.474 |
| 02 | grounding de ações legais | 42 | 511,8 | 20 | 8.688 | 3 | 4 | 0 | 14,3% | 0 | 21 | 5.938 / 15.517 |
| 03 | reason then ground | 46 | 510,4 | 89 | 8.402 | 5 | 5 | 3 | 13,0% | 0 | 46 | 16.265 / 42.264 |
| 04 | repair formal | 44 | 492,2 | 39 | 9.153 | 2 | 5 | 3 | 31,8% | 3 | 25 | 2.992 / 34.695 |
| 05 | JSON estruturado estrito | 36 | 591,4 | 19 | 9.025 | 4 | 1 | 2 | 16,7% | 1 | 19 | 2.766 / 17.339 |
| 06 | tabuleiro ASCII | 44 | 838,2 | 35 | 7.764 | 5 | 5 | 0 | 31,8% | 7 | 29 | 11.607 / 37.144 |
| 07 | histórico UCI completo | 72 | 315,2 | 42 | 8.789 | 3 | 5 | 7 | 11,1% | 2 | 38 | 9.726 / 46.975 |
| 08 | histórico SAN completo | 46 | 494,1 | 29 | 8.912 | 4 | 3 | 1 | 21,7% | 6 | 29 | 3.387 / 36.034 |
| 09 | tabuleiro RGB + FEN | 54 | 394,8 | 35 | 8.100 | 4 | 4 | 1 | 25,9% | 8 | 35 | 20.995 / 27.941 |
| 10 | checklist tático | 38 | 1.389,6 | 74 | 8.505 | 4 | 5 | 2 | 15,8% | 3 | 22 | 4.222 / 22.162 |

Os dois primeiros ensaios técnicos da 03 e da 04 foram preservados no
workspace, mas excluídos do recorte principal. A 03 original parou por
throttling do provider. A 04 original parou porque o `RepairStrategy` devolveu
`no_action`; o coordenador foi corrigido para tratar isso como tentativa
inválida e fornecer feedback legal antes de repetir.

## O que foi diferente na partida de 72 plies

A variante 07 usou:

- `chess.direct`, sem grounding, repair ou JSON estruturado;
- FEN da posição atual;
- histórico completo em UCI, desde o primeiro lance;
- nenhum conjunto explícito de ações legais;
- saída textual com uma única jogada UCI;
- MuseSpark 1.3 Free via `provider.openai_compatible`, perfil
  `openai-responses`, proxy local `opencode-router` e `reasoning_effort:
  minimal`;
- Stockfish com alvo 1000 aproximado, efetivo 1320, `Skill Level 0`, 20.000
  nodes, 1 thread e hash de 16 MB;
- `max_plies: null`, `max_calls: null`, 3 rejeições ilegais permitidas por
  turno e 5 tentativas transitórias de transporte.

O resultado foi `1. e4 d5 2. exd5 Qxd5 3. Nc3 Qe5+ 4. Be2 e6 5. Nf3 Qf6
6. d4 Bd6 7. O-O Qd8 ... 36. Kxh5 Qh3#`. O modelo jogou 36 lances; o
Stockfish respondeu 36 vezes. A partida durou mais porque a sequência do
Stockfish não produziu mate cedo, não porque o modelo tenha demonstrado força
de 72 lances.

O ponto decisivo foi `31. a4`. Na análise de 20.000 nodes, a avaliação do
modelo caiu de `-711 cp` para `-9500 cp`, uma perda de `8789 cp`. O melhor
lance registrado era `h2h3`. Depois de `31. a4 Qd4 32. Bb1 Rc1+`, o rei branco
entrou numa sequência forçada: `33. Kg2 Qd1 34. Kh3 Qf1+ 35. Kh4 Rxb1
36. Kxh5 Qh3#`.

Os outros maiores pontos críticos foram:

| lance do modelo | CPL | melhor lance SF | leitura |
| --- | ---: | --- | --- |
| 9. Nxc7+ | 423 | `c1g5` | troca material sem preservar a melhor pressão |
| 16. Qxd6 | 599 | `c1e3` | captura que piorou muito a posição |
| 25. Rc4 | 154 | `c1c8` | erro de colocação da torre |
| 29. Rc2 | 212 | `f2f3` | perdeu coordenação antes da fase final |
| 31. a4 | 8.789 | `h2h3` | entrou em mate forçado |

O score médio foi 315,2 cp, mediana 42 cp, 3 blunders, 5 erros, 7
imprecisões e 21 decisões classificadas como boas ou melhores. O modelo
coincidiu exatamente com o primeiro lance do Stockfish em 4 de 36 decisões,
11,1%. Uma decisão pode ter CPL baixo sem ser o primeiro lance do engine, por
isso CPL e acordo SF não são a mesma métrica.

## O que a cadeia auditável mostra

O `chess.direct` não produz uma cadeia de raciocínio textual no contrato do
Zugzwang. Cada chamada recebeu um único prompt de usuário com FEN, lado,
número do lance e histórico UCI. A resposta persistida em cada artifact de
modelo foi somente o UCI final, por exemplo `e2e4`, `c3b5` ou `a2a4`.

O fluxo comprovável para cada decisão foi:

1. o ambiente gerou a observação formal;
2. o adapter enviou o prompt ao proxy local;
3. o modelo devolveu um UCI;
4. o coordenador verificou a legalidade;
5. o lance legal foi commitado e o Stockfish recebeu a vez.

Houve dois retries de legalidade:

- no ply 31, `a1c1` foi recusado e o modelo respondeu `d1d6`;
- no ply 65, `b1a2` foi recusado e o modelo respondeu `g1g2`.

As duas recusas foram isoladas, portanto nenhuma atingiu quatro tentativas
ilegais consecutivas. O registro tem 38 chamadas do provider para 36 lances
do modelo. O provider informou 46.975 tokens de saída, mas o artifact
persistido contém apenas as jogadas finais. Esse contador não permite
reconstruir nem expor uma cadeia de pensamento privada.

Também não há uma semente do provider no request canônico (`seed: null`). O
seed `20261007` controla o experimento e o ambiente, mas não torna a geração
do modelo determinística. A comparação 07 contra 08, portanto, mistura o
efeito UCI versus SAN com a variação estocástica do provider.

## Leitura comparativa

Dentro desta amostra única por variante, o histórico UCI completo teve o menor
CPL médio da bateria, 315,2 cp, e a menor contagem de blunders, 3. A variante
02 veio depois, com 4; as outras tiveram 5 ou mais. Isso é um sinal promissor para contexto UCI completo,
mas ainda não é uma conclusão estatística.

O histórico SAN completo terminou em 46 plies, com CPL médio 468,5 e 5
blunders. Como 07 e 08 usaram seeds de experimento diferentes e o provider
não recebeu seed, não dá para atribuir os 26 plies extras apenas à notação
UCI. Para transformar isso em evidência, o próximo teste deve repetir cada
variante várias vezes com uma semente realmente aceita pelo provider e medir
ACPL, blunders por 100 decisões, duração até mate e taxa de acordo.

## Artefatos

- Manifesto: `experiments/musespark-stockfish-battery/07-full-uci-history.yaml`.
- Banco e CAS da bateria: `/tmp/zugzwang-musespark-battery-20260904-r2`.
- Viewer somente leitura: `viewer/index.html` e `viewer/data.js`.
- Avaliador preciso: `plugins/evaluator-stockfish/src/zgw_eval_stockfish/evaluator.py`.
- Script de avaliação real: `scripts/evaluate_real_stockfish.py`.
