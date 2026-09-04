# Relatório completo — R5 multiagente por lance

Data da análise: 2026-09-04

Run: run_9FDUejOJmPHoZVM1z5z3dw

Modelo: muse-spark-1.3-contributor, via provider.openai_compatible e roteador local OpenCode Go

Oponente: Stockfish 16 real, política de Elo aproximado 1000 (UCI_Elo 1320, Skill Level 0), Threads 1, Hash 16, limite de 20.000 nós por lance

Estratégia: chess.multi_agent_review, regime R5, H2/K0

## Resumo executivo

Foi uma partida real, sem fake backend, fake oponente ou fake evaluator. O modelo jogou de brancas contra Stockfish até mate, sem limite de lances. A partida terminou em 56 plies, com 28 decisões do modelo e mate formal de pretas: 28...Rd1#.

O fluxo multiagente funcionou como projetado no nível de orquestração:

- cada decisão normal chamou Critical Scout, Strategic Planner e Final Reviewer em ordem;
- os três papéis receberam a mesma observação completa do tabuleiro, mas não receberam lista de ações legais nem avaliação Stockfish ao vivo;
- o lance escolhido passou pelo ambiente canônico e pelo RulesKernel;
- cada tentativa de provider, resposta, wire request/response e telemetria ficou persistida;
- as três tentativas ilegais do lance 16 foram recusadas pelo ambiente, sem aplicar estado inválido.

O resultado, porém, não demonstra ganho de força. A cadeia aumentou a cobertura de inspeção tática, mas não evitou o erro decisivo 15.Bxd6. Depois de ...Bh6+, também precisou de três rejeições para finalmente encontrar 16.Kb1. O ponto mais importante para pesquisa é que a arquitetura atual é uma cadeia dependente: o Planner herda o mapa do Scout e o Reviewer herda ambos. Um erro geométrico inicial pode ser repetido, amplificado ou apenas corrigido tardiamente.

Também foi encontrado um defeito de integridade no parser de lances: no lance 2 o Reviewer emitiu Ng1f3, mas o parser antigo rejeitou o formato com prefixo de peça e capturou d2d4 no texto explicativo. O código foi corrigido e recebeu teste de regressão; esta run histórica permanece imutável como evidência do bug.

## O que é e não é reasoning nesta análise

O provider não expôs texto legível de cadeia privada de pensamento. Em 93 de 93 tentativas houve contagem de reasoning tokens e um item de reasoning criptografado, mas nenhuma delas trouxe um resumo legível. Portanto, este relatório não inventa nem chama esses campos de chain-of-thought.

O que é analisado aqui é todo o material observável e auditável: critical_map, hanging_pieces, tactical_ideas, plan, candidate_moves, preferred_move, review, riscos, lance final, histórico/FEN, respostas normalizadas, wire, telemetria numérica, eventos de rejeição e avaliação post-hoc. A extração completa está em:

/tmp/zugzwang-run-9FDUejOJmPHoZVM1z5z3dw-analysis.json

O bundle CAS verificável da run está em:

/tmp/zugzwang-real-go-multi-agent-review-full-bundle-20260904

## Configuração e fluxo real

Para cada lance das brancas, a estratégia executou:

1. Critical Scout: mapeamento do estado, peças penduradas, ideias táticas e candidatos iniciais.
2. Strategic Planner: plano de curto prazo, candidatos ordenados, riscos e preferência.
3. Final Reviewer: auditoria dos candidatos e escolha final em formato estruturado.
4. Parser e gateway: extração do lance.
5. RulesKernel/ambiente: validação formal e aplicação da transição.

As chamadas não usaram engine durante a decisão. A avaliação Stockfish foi feita depois da partida pelo evaluator.stockfish.precise v0.3.0. A observação tinha FEN, histórico UCI completo, número do lance e lado a jogar; legal_actions ficou ausente em todas as 28 observações.

A run durou aproximadamente 12 minutos e 10 segundos, de 19:41:36.820Z a 19:53:46.451Z. Foram 56 steps committed e 28 observações de decisão. Houve 31 DecisionTrace no event stream porque o lance 16 teve quatro cadeias completas: uma cadeia inicial e três novas cadeias após rejeições.

## Resultado da partida

Sequência completa:

1. e4 e5 2. d4 d6 3. Nf3 Qe7 4. Nc3 exd4 5. Qxd4 Nf6 6. Nd5 Nxd5 7. Qxd5 Nd7 8. Qc4 Ne5 9. Qc3 Nxf3+ 10. Qxf3 g6 11. Bc4 Be6 12. Bxe6 fxe6 13. Bf4 Qf7 14. O-O-O O-O-O 15. Bxd6 Bh6+ 16. Kb1 Qxf3 17. gxf3 cxd6 18. e5 Kb8 19. exd6 Rd7 20. Rd3 Bf4 21. Rd4 e5 22. Rd5 Rf8 23. Rxe5 Rxd6 24. Re6 Rfd8 25. Rxd6 Bxd6 26. Ka1 b6 27. Rg1 Bxh2 28. Rg2 Rd1#

FEN final:

1k6/p6p/1p4p1/8/8/5P2/PPP2PRb/K2r4 w - - 2 29

O modelo não venceu o Stockfish; perdeu por mate formal. A avaliação é de uma única partida e não deve ser convertida em Elo.

## Números de execução e proveniência

| Medida | Resultado |
| --- | --- |
| Steps | 56 |
| Moves do modelo | 28 |
| Cadeias de decisão | 31 |
| Chamadas lógicas de primeira passagem | 84 |
| Tentativas reais do provider | 93 |
| Chamadas por papel, incluindo retries | 31 Scout + 31 Planner + 31 Reviewer |
| Provider attempts completed | 93/93 |
| outcome_unknown | 0 |
| Rejects de lance ilegal | 3 |
| Observações persistidas | 28 |
| DecisionTrace no stream | 31 |
| Engine durante decisão | false |
| Lista de legal_actions exposta | false |
| Reasoning telemetry presente | 93/93 |
| Reasoning legível | 0/93 |
| Input tokens do provider | 60.426 |
| Output tokens do provider | 82.329 |
| Reasoning tokens reportados | 57.177 |
| Latência acumulada do provider | 724,287 s |
| Latência média/mediana | 7,788 s / 7,006 s |
| Latência p95/máxima | 12,527 s / 39,839 s |

Por papel, incluindo as três cadeias adicionais do lance 16:

| Papel | Chamadas | Input | Output | Reasoning | Latência média |
| --- | ---: | ---: | ---: | ---: | ---: |
| Critical Scout | 31 | 8.895 | 34.927 | 20.846 | 8,983 s |
| Strategic Planner | 31 | 23.147 | 21.856 | 16.901 | 6,446 s |
| Final Reviewer | 31 | 28.384 | 25.546 | 19.430 | 7,936 s |

Os 93 attempts têm referências de request canônico, request wire, response normalizada, response wire e reasoning telemetry. A reconciliação verificou 31 traces × 3 calls × 5 referências, totalizando 465 associações sem mismatch. O CAS tinha 581 artefatos e 581 arquivos, todos presentes e com SHA-256 válido.

## Avaliação Stockfish post-hoc

Evaluation run: eval_Ot6mR6tPmdcWRZ2Pe25wkQ

O evaluator produziu 352 observações métricas. Os principais números para os 28 lances do modelo:

- CPL: n=27, média 75,111, mediana 31, máximo 591;
- WDL loss: média 0,063, máximo 0,963;
- concordância com melhor lance: 10/28 = 35,7%;
- chosen rank: média 1,278 nas 18 posições em que havia rank;
- ranks: 14 em rank 1, 3 em rank 2, 1 em rank 3 e 10 sem rank;
- classes: 16 best/good, 4 inaccuracies, 6 mistakes, 1 blunder e 1 transição de mate;
- mate_after: 1.

O WDL loss fica próximo de zero em muitos lances tardios porque a posição já está amplamente ganha para pretas; isso não significa que o lance do modelo tenha sido bom. O próprio avaliador também tem uma limitação: em algumas posições engine_best_move e a primeira jogada da linha MultiPV divergem. Por isso, concordância e chosen_rank não são a mesma coisa e devem ser comparados com cautela.

## Tabela lance a lance

Os melhores lances estão em UCI, exatamente como foram persistidos pelo evaluator.

| Lance do modelo | Escolhido | Melhor Stockfish | CPL | WDL loss | Rank | Classe |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | e4 | g1f3 | 4 | 0,016 | 1 | best/good |
| 2 | d4 | g1f3 | 32 | 0,081 | 2 | best/good |
| 3 | Nf3 | c1e3 | 0 | 0 | 3 | best/good |
| 4 | Nc3 | f1b5 | 0 | 0 | 2 | best/good |
| 5 | Qxd4 | d1d4 | 0 | 0 | 1 | best/good |
| 6 | Nd5 | f1e2 | 154 | 0,963 | — | mistake |
| 7 | Qxd5 | d4d5 | 0 | 0 | 1 | best/good |
| 8 | Qc4 | c1e3 | 76 | 0,284 | — | inaccuracy |
| 9 | Qc3 | f3e5 | 0 | 0 | 1 | best/good |
| 10 | Qxf3 | e1d1 | 83 | 0,340 | 2 | inaccuracy |
| 11 | Bc4 | f1c4 | 31 | 0,024 | 1 | best/good |
| 12 | Bxe6 | f3c3 | 3 | 0,004 | 1 | best/good |
| 13 | Bf4 | c1d2 | 49 | 0,041 | — | best/good |
| 14 | O-O-O | e1c1 | 58 | 0,011 | 1 | inaccuracy |
| 15 | Bxd6 | d1d3 | 591 | 0,009 | — | blunder |
| 16 | Kb1 | c1b1 | 13 | 0 | 1 | best/good |
| 17 | gxf3 | g2f3 | 14 | 0 | 1 | best/good |
| 18 | e5 | e4e5 | 95 | 0 | 1 | inaccuracy |
| 19 | exd6 | e5d6 | 0 | 0 | 1 | best/good |
| 20 | Rd3 | h1e1 | 103 | 0 | — | mistake |
| 21 | Rd4 | d3b3 | 0 | 0 | 1 | best/good |
| 22 | Rd5 | d4d5 | 0 | 0 | 1 | best/good |
| 23 | Rxe5 | h1d1 | 287 | 0 | — | mistake |
| 24 | Re6 | e5e4 | 225 | 0 | — | mistake |
| 25 | Rxd6 | e6d6 | 4 | 0 | 1 | best/good |
| 26 | Ka1 | h1e1 | 101 | 0 | — | mistake |
| 27 | Rg1 | a1b1 | 105 | 0 | — | mistake |
| 28 | Rg2 | g1h1 | — | 0 | — | mate transition |

Na abertura, os dez lances do modelo tiveram CPL médio 34,9, mediana 2 e WDL loss médio 0,168. No meio-jogo, os 18 lances tiveram CPL médio 98,8 e mediana 49, com oito concordâncias e o único blunder. Não houve lance do modelo na fase de endgame antes do mate.

## Leitura da cadeia de decisão

### Abertura: descrição coerente, seleção razoável e primeira falha de ingestão

No primeiro lance o Scout descreveu corretamente uma posição sem tensão: nenhuma captura, nenhum cheque, reis seguros, centro vazio e desenvolvimento como objetivo. Planner e Reviewer convergiram em e2e4. A recomendação é coerente com o estado.

No segundo lance apareceu o problema de parser. A saída estruturada do Reviewer foi Ng1f3, e o Planner também preferiu Ng1f3. A ação aplicada foi d2d4 porque o parser estrito não aceitava a forma com prefixo de peça e depois procurava qualquer token UCI dentro do texto explicativo. O token d2d4 apareceu antes e foi indevidamente escolhido. O RulesKernel aplicou d2d4 legalmente, então a partida continuou, mas a decisão persistida ficou semanticamente inconsistente com o Reviewer.

Esse caso é importante: validação legal não garante fidelidade entre decisão do agente e ação aplicada. O parser agora reconhece formas como Ng1f3 e, quando existe um campo explícito de lance inválido, não cai para tokens aleatórios da justificativa. O teste de regressão cobre exatamente esse caso. A run antiga não foi reescrita.

Entre os lances 3 e 5, os agentes encontraram desenvolvimento, pressão no centro e a recaptura Qxd4. Os textos têm boa cobertura de candidatos, mas contêm variação de xadrez verbal que não necessariamente vira cálculo concreto.

### 6.Nd5: o primeiro colapso tático mensurável

Em 6.Nd5 o Scout identificou a ideia de posto avançado, fork em e7/c7 e pressão central. Planner manteve Nd5 e Reviewer confirmou. O evaluator registrou CPL 154 e WDL loss 0,963, com f1e2 como melhor Stockfish.

A falha não foi falta de candidatos; Nd5 estava explicitamente no mapa. O problema foi sobrevalorização da narrativa de fork/outpost sem verificar a continuação concreta e o custo de permitir Nxd5. A cadeia produziu mais texto sobre a ideia do que verificação da resposta forçada.

### 8.Qc4 e 10.Qxf3: cálculo parcial, mas posição ainda administrável

Em 8.Qc4 houve CPL 76. O Scout apontou Qxd6, Bb5+, Bg5 e pressão em c7/f7; Planner escolheu Qc4 e Reviewer confirmou. A posição não colapsou imediatamente, mas a escolha perdeu eficiência.

Em 10.Qxf3, a captura foi natural depois de ...Nxf3+, porém o evaluator registrou CPL 83 e rank 2. O Scout enumerou corretamente a escolha entre Qxf3 e gxf3, mas a avaliação dos efeitos de estrutura e segurança do rei ficou superficial.

### 15.Bxd6: evento decisivo da partida

A sequência crítica foi:

13.Bf4 Qf7 14.O-O-O O-O-O 15.Bxd6 Bh6+

O evaluator registrou, na sua convenção, cp_before +11 e cp_after -580, CPL 591 e classe blunder. O melhor lance era d1d3. O modelo capturou em d6 sem avaliar a resposta forçada ...Bh6+, seguida de ...Qxf3 e ...cxd6.

Os três papéis colaboraram para o erro:

- Scout identificou o bispo em d6 como peça pendurada, a dama em f7 sob pressão e a diagonal Bh6-c1 como ameaça potencial, mas tratou a captura Qxf7 como prioridade e não fechou a sequência ...Bh6+.
- Planner preferiu Bxd6 como captura de oportunidade e descreveu a posição em termos de tensão e pressão, sem calcular o recurso forçado contra o rei.
- Reviewer confirmou Bxd6 como uma escolha plausível, apesar de a diagonal h6-c1 estar prestes a se tornar decisiva.

Este é o melhor exemplo de que três papéis sequenciais não equivalem a três opiniões independentes. O Reviewer vê a mesma representação textual já enviesada pelo Scout e pelo Planner; não existe uma etapa de adversarial challenge independente nem uma obrigação estruturada de enumerar todas as respostas forçadas do oponente.

### 16...Bh6+: três rejeições e recuperação local

Depois de ...Bh6+, o rei branco estava em cheque na diagonal h6-g5-f4-e3-d2-c1. O fluxo de retries produziu:

| Cadeia | Reviewer | Resultado |
| ---: | --- | --- |
| 1 | f3f7 | rejeitado: não responde ao cheque |
| 2 | d6c7 | rejeitado: não responde ao cheque |
| 3 | f3f7 | rejeitado novamente |
| 4 | c1b1 | aceito |

Nas três primeiras cadeias, o Scout ainda falava da dama em f7 e do bispo em d6, mas não tratava o cheque como restrição dominante. O Planner seguiu essas prioridades e o Reviewer chegou a chamar Qxf7 de “best”. O ambiente recusou os lances porque não resolviam o cheque.

Na quarta cadeia, o Scout finalmente mapeou corretamente a diagonal e os blocos possíveis f4, e3 e d2, além da fuga Kb1. Planner e Reviewer convergiram em c1b1. O RulesKernel aplicou o lance e a partida prosseguiu.

Isso mostra uma propriedade boa e uma limitação:

- propriedade boa: nenhum lance ilegal contaminou o estado; o retry foi visível, persistido e limitado pelo contrato;
- limitação: o retry não foi uma correção cognitiva garantida. Ele reexecutou o mesmo modelo em uma nova tentativa e consumiu nove chamadas extras, até que o próprio modelo reconstruísse o cheque.

### Meio-jogo: correções geométricas pontuais, mas sem prevenção de mate

Em 18.e5, o Scout chamou Rxd6+ de cheque embora a posição não desse cheque; Reviewer corrigiu a direção e escolheu e5. Em 20.Rd3, o Scout/Planner consideraram Rxd7 apesar de o peão branco em d6 bloquear a geometria; Reviewer escolheu Rd3. Em 22.Rd5, Planner sugeriu d6d7 numa casa ocupada por peça preta; Reviewer corrigiu para Rd5. Em 26.Ka1, Planner sugeriu h1h2 embora h2 estivesse ocupado; Reviewer corrigiu para Ka1.

Esses exemplos mostram que a revisão final funciona como filtro de erros locais de geometria, mas de maneira reativa. Ela não detectou o erro decisivo em 15.Bxd6 porque a falha já estava no mapa estratégico.

Nos lances 20, 23, 24, 26 e 27, os custos cresceram: CPL 103, 287, 225, 101 e 105. A sequência de torres manteve atividade, mas perdeu coordenação defensiva. Os agentes continuaram gerando ideias de ataque e invasão em d-file/h-file, enquanto o Stockfish explorava a vulnerabilidade do rei e da primeira fileira.

No lance 28, o Scout percebeu a ameaça concreta Bxg1 e que a torre em g1 precisava sair da diagonal. Planner e Reviewer escolheram Rg2, que salva a torre localmente. O que faltou foi elevar a busca para a ameaça global: depois de Rg2, 28...Rd1# é mate. A cadeia resolveu a peça pendurada, mas não comparou a segurança do rei após o lance. Esse é um caso claro de otimização local de material contra requisito terminal de king safety.

## Padrões de comportamento dos papéis

O Scout gerou 84 entradas de peças penduradas e 146 ideias táticas contando as cadeias finais e os retries. Isso comprova que o papel força uma varredura explícita, mas não comprova a qualidade dessa varredura. Foram observados:

- “sem defensor” tratado como sinônimo de “atualmente atacado”;
- possibilidades de en passant onde não havia condição;
- confusão entre linhas de bispo, casas ocupadas e checks;
- listas longas de candidatos que não eram filtradas por resposta forçada.

O Planner herdou esse mapa e adicionou objetivos de desenvolvimento, pressão de arquivo e segurança do rei. Em 25 dos 28 ciclos finais, a preferência textual do Planner e a escolha do Reviewer coincidiram. Isso indica alta dependência, não consenso independente.

O Reviewer alterou ou corrigiu a direção nos casos mais visíveis:

- lance 5: Planner apontou Nd5, Reviewer preferiu Qxd4;
- lance 22: Planner sugeriu d6d7, Reviewer corrigiu para Rd5;
- lance 26: Planner sugeriu h1h2, Reviewer corrigiu para Ka1.

O Reviewer também coincidiu com o trace final persistido em 27 de 28 decisões. A exceção é o lance 2, causada pelo parser antigo, não por divergência do modelo.

## Diagnóstico arquitetural

O R5 atual é uma pipeline serial dependente:

Scout → Planner → Reviewer → parser → RulesKernel

Ele melhora a legibilidade dos papéis e a auditabilidade, mas não oferece ainda:

- voto independente entre agentes;
- comparação obrigatória de respostas forçadas do adversário;
- verificador independente de geometria antes do Reviewer;
- orçamento adaptativo baseado em criticidade;
- distinção entre “candidato narrado” e “linha calculada”;
- baseline pareado com uma única chamada usando o mesmo orçamento;
- ablação que separe ganho de decomposição de ganho de mais tokens.

A run mostrou também que legalidade e qualidade são camadas diferentes. O gateway bloqueou 3 ações ilegais, mas não bloqueou Bxd6, Nd5 ou Rg2 porque eram lances legais. A avaliação post-hoc é essencial para medir essa parte.

## Integridade dos dados e correção realizada

Os artefatos da run são suficientes para reconstruir o estado lance a lance:

- 28 ObservationArtifacts com schema zgw.observation/v1;
- histórico completo e FEN em cada decisão;
- 31 DecisionTrace, incluindo todos os retries;
- 93 respostas normalizadas e 93 respostas wire;
- 93 requests wire, com deduplicação CAS resultando em 92 objetos únicos;
- 93 ReasoningTelemetry;
- 57 estados de tabuleiro;
- 1 manifest e 1 evaluation trace;
- nenhum artefato órfão, ausente ou com hash divergente.

Durante a análise foi corrigido o parser em multi_agent_review.py para:

- reconhecer lance UCI com prefixo de peça, como Ng1f3;
- rejeitar um campo explícito de move inválido em vez de procurar um UCI arbitrário na explicação;
- associar o request_fingerprint ao CallRecord das novas execuções, facilitando identificar o papel diretamente na trace.

O teste unitário cobre a regressão Ng1f3 versus d2d4. A correção não altera a run histórica nem tenta “consertar” seus artefatos.

## Conclusões para a pesquisa

1. O principal gargalo não foi falta de geração de candidatos; foi verificação concreta de respostas forçadas e segurança terminal.
2. A arquitetura de três papéis torna a decisão auditável, mas a dependência serial permite que o erro inicial atravesse todas as camadas.
3. O retry de ilegalidade preserva a integridade do tabuleiro, porém não é evidência de aprendizado ou autocorreção robusta.
4. Bxd6 é o evento causal mais forte para explicar a derrota; os erros tardios agravam uma posição já ruim.
5. Rg2 mostra uma segunda classe de falha: salvar a peça ameaçada sem avaliar se o lance permite mate imediato.
6. A run não permite afirmar que R5 é melhor ou pior que R0. É necessário um experimento pareado, com mesma posição, mesma semente/condições e orçamento explícito.

## Próximos experimentos recomendados

- Rodar R0 e R5 em pares com a mesma abertura/posição e mesmo teto de tokens.
- Adicionar uma etapa independente “forced-reply auditor” apenas quando houver cheque, captura forçada, ameaça de mate ou peça pendurada crítica.
- Exigir no schema do Scout uma seção separada para checks do lado a jogar, checks do adversário e respostas forçadas.
- Fazer o Reviewer responder explicitamente: “qual é o melhor contra-lance do oponente após este candidato?”.
- Medir retries ilegais, CPL, mate rate, WDL loss e custo por decisão juntos.
- Fazer ablação Scout-only, Scout+Planner e Scout+Planner+Reviewer para separar decomposição de simples aumento de chamadas.
- Corrigir e acompanhar a comparação engine_best_move versus primeira jogada MultiPV antes de usar chosen_rank como métrica principal.
- Repetir a bateria em Stockfish aproximado 1000, 1500 e 2000, sempre marcando que o nível UCI é aproximação e não Elo oficial.

## Registro de conclusão

status: concluído

changed_paths: packages/zugzwang-chess/src/zugzwang_chess/strategies/multi_agent_review.py; tests/unit/test_multi_agent_review.py; docs/reports/R5-MULTI-AGENT-RUN-2026-09-04.md

tests: análise CAS, replay independente de legalidade e reconciliação de 465 referências concluídos; 223 testes passaram, 1 foi pulado, 6 opt-in foram deselecionados; Ruff, formatação, Pyright e foundation validator passaram

requirements_satisfied: run real sem limite até mate; três papéis explícitos; Stockfish post-hoc; dados por nó persistidos; análise independente por subagents; limitações declaradas

invariants_checked: sem engine live; sem legal_actions expostas; sem fallback oculto; todos os lances aplicados legais; todos os 93 attempts completed; hashes CAS válidos

decisions_needed: escolher baseline R0 pareado e orçamento da próxima ablação; decidir se o forced-reply auditor entra como R5.1

risks: uma run não mede força; WDL tardio satura; chosen_rank tem divergência de PV em alguns pontos; raciocínio privado não é observável

follow_up: repetir com ablação e atualizar a UI para abrir esta run e seus artefatos locais
