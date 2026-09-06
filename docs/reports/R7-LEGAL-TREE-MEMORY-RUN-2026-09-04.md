# Run R7 legal tree e memória persistida

Data: 2026-09-04

Run: run_kYRs9O0z2yB8ZrQobZefww

Modelo: muse-spark-1.3-contributor, via provider.openai_compatible no roteador OpenCode local

Esforço de reasoning: low

Oponente: Stockfish 16 real, Elo aproximado 1000, UCI_Elo 1320, Skill Level 0, 20.000 nós, uma thread

Estratégia: chess.legal_tree_memory, R7, memória persistent, H4/K6

## Resultado

A partida completou 48 plies em aproximadamente 17 minutos e 44 segundos. O
modelo jogou de brancas e perdeu por mate formal de pretas em 24...Qxg2#.

FEN final:

6k1/p2b1ppp/6n1/3p1p2/5P2/8/PPr3q1/R6K w - - 0 25

PGN principal:

1. e4 d5 2. exd5 e6 3. d6 c5 4. Bb5+ Nc6 5. Bxc6+ bxc6 6. Nf3 Bxd6
7. O-O Ne7 8. Re1 O-O 9. Nc3 Ng6 10. Nd5 cxd5 11. Qe2 Bd7 12. d4 cxd4
13. Nxd4 Rc8 14. Nf5 Bxh2+ 15. Kxh2 exf5 16. Qe8 Rxe8 17. Rxe8+ Qxe8
18. f4 Qe2 19. Kg1 Qd1+ 20. Kh2 Qh5+ 21. Kg1 Rxc2 22. Be3 Qe2
23. Bf2 Qxf2+ 24. Kh1 Qxg2#

## Execução

| Medida | Resultado |
| --- | ---: |
| Plies | 48 |
| Turnos do modelo | 24 |
| Calls do provider | 72 |
| Calls por papel | 24 Mapper + 24 Analyst + 24 Reviewer |
| Calls completas | 72/72 |
| Falhas de provider | 0 |
| Rejeições de lance final | 0 |
| SearchWorkspaces | 24 |
| Eventos de retrieval | 216 |
| Eventos de enumeração gateway | 113 pares request/completed |
| Arestas de busca propostas | 246 |
| Arestas legais committed | 178 |
| Arestas ilegais rejeitadas | 68 |
| Effective assistance | H4/K6 |

O gateway enumerou o conjunto legal da posição raiz em cada turno. Para cada
ramificação legal, o lease foi rebindado ao estado hipotético e o conjunto
legal de respostas também foi enumerado. O modelo nunca recebeu Stockfish ou
artefato de avaliação durante a decisão.

O conjunto ilegal não foi tratado como enumerável. Foram registrados somente
probes ilegais que o modelo propôs e o RulesKernel rejeitou.

## Tokens e telemetria

| Papel | Calls | Input | Output | Reasoning | Latência média |
| --- | ---: | ---: | ---: | ---: | ---: |
| Position Mapper | 24 | 29.960 | 51.871 | 43.079 | 16,856 s |
| Variant Analyst | 24 | 69.895 | 41.958 | 34.427 | 14,923 s |
| Final Reviewer | 24 | 87.169 | 34.369 | 29.660 | 12,341 s |

Totais: 187.024 input tokens, 128.198 output tokens e 107.166 reasoning
tokens reportados pelo provider. As 72 tentativas têm reasoning telemetry,
mas nenhuma tem reasoning_summary legível. O relatório analisa as saídas
estruturadas e a telemetria exposta, não chain-of-thought privado.

## Memória persistida

O primeiro turno começou sem notas. A partir do segundo, o Reviewer recebeu
notas recuperadas da memória persistida do episódio. Em geral foram 8 a 10
itens por turno.

Os hits vieram principalmente de root_move e refutation. exact_state ficou
frequentemente vazio porque a posição raiz muda depois de cada lance, mas os
source position keys permitem recuperar uma nota quando a posição volta a
coincidir. A memória acumulou candidatos e respostas de variantes sem cruzar
episódios.

O conteúdo persistido é composto por notas controladas pelo SearchMemoryFabric.
Stockfish, tablebase e evaluation:// foram rejeitados pelo firewall.

## Evolução por turno

| Turno | Lance | Ações legais | Memória recuperada | Raízes | Variantes | Probes ilegais |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | e2e4 | 20 | 0 | 4 | 4 | 3 |
| 2 | e4d5 | 31 | 8 | 4 | 4 | 3 |
| 3 | d5d6 | 31 | 8 | 4 | 4 | 3 |
| 4 | f1b5 | 30 | 8 | 4 | 4 | 3 |
| 5 | b5c6 | 33 | 8 | 4 | 4 | 3 |
| 6 | g1f3 | 26 | 10 | 4 | 4 | 3 |
| 7 | e1g1 | 25 | 8 | 4 | 4 | 3 |
| 8 | f1e1 | 23 | 8 | 4 | 4 | 3 |
| 9 | b1c3 | 27 | 10 | 4 | 4 | 3 |
| 10 | c3d5 | 30 | 8 | 4 | 4 | 2 |
| 11 | d1e2 | 26 | 8 | 4 | 4 | 2 |
| 12 | d2d4 | 31 | 10 | 4 | 4 | 3 |
| 13 | f3d4 | 36 | 8 | 4 | 4 | 2 |
| 14 | d4f5 | 42 | 8 | 4 | 4 | 3 |
| 15 | g1h2 | 3 | 8 | 3 | 3 | 2 |
| 16 | e2e8 | 40 | 10 | 4 | 4 | 3 |
| 17 | e1e8 | 31 | 10 | 4 | 4 | 3 |
| 18 | f2f4 | 20 | 10 | 4 | 4 | 3 |
| 19 | h2g1 | 13 | 8 | 4 | 4 | 3 |
| 20 | g1h2 | 2 | 8 | 2 | 2 | 2 |
| 21 | h2g1 | 2 | 8 | 2 | 2 | 3 |
| 22 | c1e3 | 10 | 8 | 4 | 4 | 3 |
| 23 | e3f2 | 20 | 8 | 4 | 4 | 3 |
| 24 | g1h1 | 2 | 10 | 2 | 2 | 3 |

As listas de candidatos e variantes não são avaliações de força. Elas são a
evidência do que os agentes colocaram em análise naquele turno.

## Avaliação Stockfish pós-jogo

Evaluation run: eval_7JbW2q2r-SwMSlAy8kYmtQ

Evaluator: evaluator.stockfish.precise v0.3.0

Foram produzidas 285 observações métricas:

- CPL em 18 comparações: média 108,056, mediana 36, máximo 683;
- WDL loss em 24 lances: média 0,063, máximo 0,877;
- acordo com o melhor lance: 8/24, ou 33,3%;
- chosen rank disponível em 13 lances: média 1,385;
- classes: 12 best/good, 1 inaccuracy, 3 mistakes, 2 blunders e 6 transições de mate;
- mate_after em 6 lances e mate_before em 4.

| Lance do modelo | Jogado | Melhor Stockfish | CPL | Classe |
| ---: | --- | --- | ---: | --- |
| 1 | e4 | e2e4 | 4 | best/good |
| 2 | exd5 | e4d5 | 35 | best/good |
| 3 | d6 | f1b5 | 143 | mistake |
| 4 | Bb5+ | b1c3 | 36 | best/good |
| 5 | Bxc6+ | b5c6 | 13 | best/good |
| 6 | Nf3 | d1f3 | 41 | best/good |
| 7 | O-O | d2d3 | 18 | best/good |
| 8 | Re1 | b1c3 | 0 | best/good |
| 9 | Nc3 | b1a3 | 44 | best/good |
| 10 | Nd5 | c3e4 | 683 | blunder |
| 11 | Qe2 | h2h4 | 53 | inaccuracy |
| 12 | d4 | h2h4 | 25 | best/good |
| 13 | Nxd4 | f3d4 | 35 | best/good |
| 14 | Nf5 | h2h4 | 149 | mistake |
| 15 | Kxh2 | g1h2 | 17 | best/good |
| 16 | Qe8 | e2h5 | 428 | blunder |
| 17 | Rxe8+ | e1e8 | 0 | best/good |
| 18 | f4 | c1d2 | 221 | mistake |

Depois de 18.f4, o evaluator já registrou uma sequência de mate para pretas.
Os seis lances restantes do modelo são respostas em uma posição com mate
forçado, por isso aparecem como transições de mate sem CPL comparável.

## Leitura do processo agentic

Mapper, Analyst e Reviewer concordaram na maior parte das decisões, mas isso
não significa independência estatística. O Analyst recebe o mapa do Mapper e
o Reviewer recebe os dois relatórios.

Houve divergência explícita em alguns pontos:

- no turno 4, o Analyst preferiu b1c3 e o Reviewer escolheu f1b5;
- no turno 12, o Analyst preferiu f3g5 e o Reviewer escolheu d2d4;
- no turno 14, o Analyst preferiu d4e6 e o Reviewer escolheu d4f5;
- no turno 18, o Analyst preferiu c1e3 e o Reviewer escolheu f2f4;
- no turno 19, o Analyst preferiu h2h3 e o Reviewer escolheu h2g1.

O sistema detectou e persistiu 68 arestas ilegais dentro das variantes. Isso
mostra que o modelo explorou ações fora do conjunto legal em hipóteses locais,
mas a validação formal impediu que qualquer uma entrasse no tabuleiro real.

O ponto fraco foi qualidade de cálculo, não grounding. Mesmo vendo todas as
ações legais, o agente escolheu 10.Nd5 e 16.Qe8, os dois maiores blunders da
run. O tree ajudou a testar geometria e respostas locais, mas a profundidade
de duas plies não foi suficiente para perceber a consequência terminal de
18.f4.

## Incidentes antes da run concluída

As tentativas anteriores ficaram preservadas:

- run_KS2IRJzd7mymWJN0lX6W9w: falhou no primeiro turno porque o schema do
  Position Mapper não tinha additionalProperties=false no objeto interno de
  hanging_pieces. O provider real devolveu erro 400 nas quatro tentativas.
- run_tMUrbA_KegDS2eXmWH-kJg: chegou a 14 plies, mas terminou após quatro
  ciclos sem ramo legal no turno seguinte.
- run_y_Nj5JCsGY4wb7F3O7ZHcA: foi cancelada quando o limite de saída mudou de
  4096 para 16384. Seus artefatos não foram apagados.

A run final com 16384 eliminou o truncamento de reasoning low e completou sem
falha de provider.

## Integridade e correção posterior

O CAS exportado contém 486 entradas de checksum e todas foram verificadas.
Cada tentativa real tem request, response, wire e reasoning telemetry. A
partida final não possui retries ilegais.

Na auditoria, encontrei uma colisão de IDs na projeção SQL: node e edge IDs
eram derivados apenas da trajetória, então árvores de sessões diferentes
podiam usar a mesma chave primária. O CAS por sessão continuava completo, mas
o projection SQL perdeu 8 nós e 9 arestas repetidos.

Corrigi os IDs para incluir o search_session_id e adicionei testes que criam
duas sessões com a mesma posição. A run histórica não foi reescrita; ela fica
como evidência do comportamento antigo, com o CAS íntegro.

## UI e artefatos

A UI somente leitura foi atualizada e aberta na partida final. Ela mostra os
48 plies, PGN, modelo, Stockfish, tokens, CPL e 285 observações.

Bundle privado:

/tmp/zugzwang-r7-persistent-full-low-bundle-20260904

JSON de avaliação operacional:

/home/maelrx/Documents/ChatGPT/Zugzwang/.zugzwang/state.db

## Conclusão

O R7 conseguiu fazer o que queríamos no plano de infraestrutura: legalidade,
ramificações, retrieval, memória persistida e proveniência por turno ficaram
visíveis e auditáveis. A partida não mostra melhora de força. Ela mostra que
grounding perfeito e memória disponível não substituem cálculo de respostas
forçadas.

O próximo teste científico correto é parear esta condição com memória
episódica usando a mesma abertura, o mesmo modelo, o mesmo reasoning low e o
mesmo budget. Depois, repetir a comparação com profundidade 4 e com uma etapa
independente de auditoria de checks e mates.
