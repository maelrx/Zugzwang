# Relatório científico — partida H3 do agente único com árvore legal

Data da análise: 2026-09-05  
Run: `run_VLIjksKehECzZhu2GLuAsQ`  
Condição: `h3-persistent-forced-replies` (`cnd_2c52c1bb78b89c17`)

## Resposta curta

Sim. Nesta partida específica, o modelo venceu formalmente o Stockfish
configurado: jogou de brancas e terminou com `46.Rb8#`. O FEN final foi

```text
1Rk5/3b4/R2B4/p7/6P1/7P/P4P1K/8 b - - 6 46
```

Uma verificação independente com `python-chess` confirmou lado a jogar pretas,
xeque, xeque-mate, não afogamento e zero lances legais restantes.

Isso é uma vitória real contra o oponente da condição, mas não é evidência de
que o MuseSpark derrotou Stockfish em força máxima. O adversário era Stockfish
16 com `UCI_Elo=1320`, `Skill Level=0` e limite de 20.000 nodes, uma aproximação
operacional do alvo solicitado como Stockfish 1000.

## 1. Protocolo reproduzido

| Campo | Valor |
| --- | --- |
| Modelo | `muse-spark-1.3-contributor` |
| Rota | `provider.openai_compatible` → `opencode-router` local |
| Estratégia | `chess.single_agent_tree`, R7 |
| Cor do modelo | Brancas |
| Reasoning | `medium` |
| Teto de saída | 32.768 tokens |
| Memória | persistente, K6 |
| Prompt | checklist de checks, capturas, mates e fugas do rei |
| Raízes | até 4 candidatas; replies legais em todas as raízes |
| Profundidade formal | 2 plies |
| Oponente | Stockfish 16 real |
| Força durante a partida | requested 1000; UCI Elo efetivo 1320; Skill 0 |
| Limite do engine | 20.000 nodes, 1 thread, Hash 16 MB |
| Cap operacional | 120 plies / 600 calls |
| Resultado | 91 plies, partida completa, mate das pretas |

O run começou em `2026-09-04T23:18:09.385Z` e terminou em
`2026-09-05T00:03:23.554Z`. Foram 46 decisões do modelo, 45 respostas do
Stockfish e 46 chamadas do provider. Todas as tentativas foram concluídas; não
houve retry ou falha de provider nesta partida.

## 2. Partida completa

```text
1. e4 Nf6 2. e5 Nd5 3. d4 Nc6 4. c4 Nf6
5. exf6 e6 6. Bg5 gxf6 7. Bh4 Bb4+ 8. Nc3 Bxc3+
9. bxc3 d5 10. Nf3 dxc4 11. Bxc4 Ne7 12. Bxf6 Rf8
13. O-O Rg8 14. Ne5 Qd6 15. Qh5 Qxe5 16. Bxe5 Kd8
17. Bxc7+ Kd7 18. Be5 Rg6 19. Bxe6+ Kxe6 20. d5+
Nxd5 21. Qxh7 Ne7 22. Rae1 Nf5 23. Bd4+ Kd6 24. Be5+
Kc6 25. Qxg6+ fxg6 26. c4 Nd6 27. Bxd6 Bd7 28. c5 b6
29. Re5 Bf5 30. Rfe1 Bg4 31. h3 Bf5 32. Kh2 a5 33. g4
Bd3 34. R1e3 Bc2 35. Rc3 Ba4 36. Be7 Kb7 37. c6+
Bxc6 38. Re6 Bd7 39. Rxg6 Be8 40. Rf6 Bd7 41. Rcc6
Ra6 42. Rxb6+ Ka8 43. Rxa6+ Kb7 44. Rfb6+ Kc7
45. Bd6+ Kc8 46. Rb8#
```

## 3. Evolução material

O modelo não ganhou de uma posição equilibrada até o mate. A própria linha do
Stockfish de baixa força permitiu uma vantagem material cedo, e o modelo a
converteu apenas no final.

| Momento | Lance | Material branco − preto | Leitura |
| ---: | --- | ---: | --- |
| 5 | `exf6` | +3 | o peão branco captura o cavalo em f6 |
| 6... | `gxf6` | +2 | pretas recuperam o peão, mas continuam sem a peça |
| 17 | `Bxc7+` | +10 | a posição já é materialmente dominante |
| 25 | `Qxg6+` | +13 | a dama captura a torre antes da recaptura |
| 25... | `fxg6` | +4 | a dama branca é sacrificada; a margem cai bastante |
| 41 | `Rcc6` | +7 | duas torres pressionam a sexta fileira |
| 42 | `Rxb6+` | +8 | remoção do defensor de b6 |
| 43 | `Rxa6+` | +13 | captura da torre preta em a6 |
| 46 | `Rb8#` | +13 | mate com torres e bispo coordenados |

O ponto causal é `5.exf6`: a partida já não era um teste de conversão a partir
de igualdade depois que a linha preta permitiu a perda do cavalo.

## 4. Avaliação pós-jogo com Stockfish real

Foram executadas duas avaliações independentes sobre os mesmos 46 lances do
modelo. A avaliação não entrou no prompt durante a partida.

### 4.1. Mesma força do oponente

Evaluation run: `eval_ieuERp5WwaP7N7cb0C6nyQ`  
Stockfish 16, UCI Elo 1320, Skill 0, 20.000 nodes, MultiPV 3.

| Métrica | Resultado |
| --- | ---: |
| Observações | 569 |
| CPL comparável | n=43, média 66,721, mediana 39, máximo 448 |
| WDL loss | n=45, média 0,011, máximo 0,375 |
| Acordo estrito com o melhor lance | 9/46 = 19,6% |
| Classes | 27 best/good, 8 inaccuracies, 7 mistakes, 1 blunder, 3 none |

### 4.2. Stockfish 16 em força máxima

Evaluation run: `eval_6NXFgTSWHu4izmd5EIkgHg`  
Stockfish 16, sem `UCI_LimitStrength`, Skill 20, 20.000 nodes, MultiPV 3.

| Métrica | Resultado |
| --- | ---: |
| Observações | 571 |
| CPL comparável | n=43, média 61,209, mediana 23, máximo 445 |
| WDL loss | n=45, média 0,008, máximo 0,257 |
| Acordo estrito com o melhor lance | 20/46 = 43,5% |
| Rank do lance | n=29, média 1,483, mediana 1 |
| Classes | 31 best/good, 5 inaccuracies, 6 mistakes, 1 blunder, 3 none |

Os dois árbitros concordam no principal desvio: `25.Qxg6+` foi o único
blunder explícito. O resultado final, entretanto, não dependeu de jogar sempre
o primeiro lance do engine. Na posição imediatamente anterior ao mate, o
Stockfish encontrou `Ra8#` e o modelo escolheu `Rb8#`; ambos são mates. Por
isso, o indicador de acordo estrito subestima decisões equivalentes quando há
mais de um mate vencedor.

### 4.3. Lances críticos

| Lance do modelo | CPL baixo | CPL máximo | Melhor lance máximo | Classe | Interpretação |
| ---: | ---: | ---: | --- | --- | --- |
| `17.Bxc7+` | 210 | 194 | `Qxf7`/`Qh5` conforme a linha | mistake | pressão correta, mas não a conversão mais precisa |
| `19.Bxe6+` | 187 | 286 | `Bb5` | mistake | ataque natural que deixa eficiência na mesa |
| `23.Bd4+` | 285 | 284 | `Bf4`/`c7` | mistake | cheque natural, mas não o mais forte |
| `25.Qxg6+` | 448 | 445 | `Qxf7` | blunder | troca a dama por uma torre apesar de já estar ganho |
| `41.Rcc6` | 263 | 235 | `Rd6` | mistake | ataque de duas torres, mas perde precisão |
| `42.Rxb6+` | 141 | 127 | `Rd6` | mistake | continua ganhando, porém prolonga a conversão |
| `46.Rb8#` | sem CPL comparável | mate | `Ra8#`/`Rb8#` | mate | vitória formal; duas soluções de mate |

O lance `25.Qxg6+` explica a diferença entre “venceu” e “jogou como um
engine”. O modelo identificou corretamente um cheque e uma captura de torre,
mas avaliou mal o custo da recaptura `...fxg6`. A própria saída estruturada
registrada no trace dizia que `Qxg6+` era o cheque direto mais seguro; essa
hipótese estava errada segundo os dois árbitros, embora a posição continuasse
vencedora após `25...fxg6`.

## 5. Evolução por fase

Fases definidas por número do lance: abertura 1–10, meio-jogo 11–30,
final 31+.

| Fase | Lances do modelo | CPL médio baixo | CPL médio máximo | Leitura |
| --- | ---: | ---: | ---: | --- |
| Abertura | 10 | 14,8 | 15,1 | execução muito sólida, com ganho material cedo |
| Meio-jogo | 20 | 98,5 | 93,7 | maior concentração de imprecisões, mistakes e o blunder |
| Final | 16 | 60,6 | 46,7 | conversão irregular, mas suficiente para o mate |

O modelo foi mais forte quando a posição tinha táticas locais claras e
material já ganho. Foi menos confiável ao comparar uma captura forçante com uma
continuação de preservação de material e segurança do rei.

## 6. O que o agente realmente recebeu e fez

Cada decisão teve exatamente uma chamada do modelo. O trace estruturado
persistiu `critical_map`, peças penduradas, ideias táticas, candidatas,
probes ilegais, variantes, análise e confiança. A análise usa esses campos e
a telemetria exposta; não afirma recuperar chain-of-thought privado.

### Cobertura formal

- 46 SearchWorkspaces, um por decisão branca;
- 46 eventos por retriever para cada um dos 9 retrievers: 414 eventos de
  retrieval;
- 1.616 pedidos e 1.616 conclusões de enumeração do gateway;
- 46 validações finais do lance escolhido;
- 2.119 arestas propostas, 1.726 committed e 393 rejeitadas no event ledger;
- profundidade formal máxima 2 plies;
- nenhum Stockfish, tablebase ou métrica pós-jogo foi disponibilizado ao
  modelo durante a partida.

### Telemetria provider

| Medida | Total |
| --- | ---: |
| Input tokens | 310.288 |
| Output tokens | 434.018 |
| Reasoning tokens reportados | 395.660 |
| Latência média | 58,769 s |
| Latência mediana | 61,900 s |
| Latência máxima | 98,184 s |

Nos traces, a média foi de aproximadamente 4,72 candidatas, 4,89 ideias
táticas, 3,35 variantes e 2,98 probes ilegais por decisão. A confiança
estruturada média foi 0,817; no lance final foi 1,0.

### Pontos de decisão representativos

**Abertura — 1.e4.** O agente mapeou a posição simétrica, escolheu e4 entre
quatro candidatas e identificou corretamente que não havia checks, capturas ou
ameaças imediatas. O lance foi best/good nos dois árbitros.

**Meio-jogo — 25.Qxg6+.** O mapa registrou o rei preto exposto, as torres em
g6/a8 e a ideia de cheque. O erro foi de avaliação de troca: o agente preferiu
a linha visualmente forçante sem preservar a dama. A árvore legal garantiu que
o lance fosse legal, mas não produziu uma avaliação material suficientemente
profunda.

**Final — 41.Rcc6.** O agente descreveu a ideia correta de atacar b6 com duas
torres e percebeu que `Kxc6` era ilegal por causa da defesa de Rf6. O engine
preferia uma coordenação diferente (`Rd6`), mas a ideia escolhida continuou
ganhadora.

**Mate — 46.Rb8#.** O agente explicitou duas mates: `Rb8+` e `Ra8+`. Também
enumerou as fugas `Kxb8`, `Kc7`, `Kb7`, `Kd8`, bloqueios e captura pelo bispo;
as respostas foram todas eliminadas formalmente. A posição final confirma a
previsão: não existe resposta legal.

## 7. Resposta causal à pergunta “o modelo ganhou mesmo?”

Sim, no sentido operacional e formal da partida:

1. o modelo era White;
2. o oponente era o Stockfish real configurado no manifesto;
3. todos os 91 plies foram confirmados pelo RulesKernel;
4. o último lance foi legal e escolhido pelo modelo;
5. esse lance colocou o rei preto em xeque-mate;
6. a verificação independente encontrou zero lances legais para as pretas.

A conclusão correta não é “MuseSpark é mais forte que Stockfish”. A conclusão
correta é:

> Sob esta configuração de baixa força aproximada, em uma amostra, o agente
> único com árvore legal venceu uma partida completa, após obter vantagem
> material cedo e converter a posição com uma combinação final de torres e
> bispo.

O jogo também mostra que grounding perfeito não equivale a cálculo perfeito:
houve um blunder robusto em `25.Qxg6+`, sete mistakes/inaccuracies relevantes
na avaliação de baixa força e apenas 43,5% de acordo estrito com Stockfish em
força máxima.

## 8. Limitações e próximo teste correto

- uma única partida não estima taxa de vitória, Elo ou significância;
- `UCI_Elo=1320` é um modo aproximado do Stockfish, não uma medição de Elo;
- 20.000 nodes e Skill 0 não representam Stockfish em força máxima;
- CPL, rank e best-move agreement são avaliações pós-jogo e nunca foram
  fornecidos ao agente;
- traces estruturados não são chain-of-thought privado;
- `best_move_agreement` não distingue automaticamente duas mates equivalentes;
- a condição H3 mistura memória persistida com o checklist forced-replies,
  portanto não isola memória sozinha.

O próximo teste científico é um pareamento controlado: mesma abertura, mesma
seed, mesmo modelo, mesma força do Stockfish e mesmo orçamento, comparando H1
episódico contra H3 persistente/forced-replies, com pelo menos 20 partidas por
condição. A métrica primária deve ser resultado/mate rate; CPL, WDL loss,
blunders, duração e custo ficam como métricas secundárias.

## Proveniência

- Run: `run_VLIjksKehECzZhu2GLuAsQ`
- Episode: `ep_zyFAeDvqVf3miQpyaYQcIw`
- Exact-opponent evaluation: `eval_ieuERp5WwaP7N7cb0C6nyQ`
- Maximum-strength reference: `eval_6NXFgTSWHu4izmd5EIkgHg`
- Stockfish binary SHA-256:
  `00628bd9c9855c1b7ff93d7f8d51b413586cdc6336fe637f9a14a61531a05aca`
- FEN final: `1Rk5/3b4/R2B4/p7/6P1/7P/P4P1K/8 b - - 6 46`
- Evidência: SQLite/CAS local em `.zugzwang/`, com requests/responses redacted
  e traces por decisão.
