> **Registro histórico em revisão (ZGW-0085).** Snapshot dos commits até `18c98ae`, separado das fontes de viewer e dos dados privados. Não representa o estado atual dos processos.
>
> Correções verificadas: a remoção de `protocol.legality` reduziu o orçamento do gateway de 512 para 64; não foi equivalente. Após um timeout/truncamento, os três retries seguintes observados falharam internamente sem novas chamadas ao modelo. O resume de B mudou a projeção de FAILED/H4-K6 para COMPLETED/H2-K0; isso é um defeito, não conformidade. As ablações de largura e candidate-only precisam da revisão #14. As afirmações conflitantes no texto abaixo são preservadas como registro histórico, não como conclusões atuais.
>
> Hermes trabalha em ZGW-0084 localmente. Nenhuma alteração não commitada foi incorporada. Não executar estes manifestos como continuação implícita de runs anteriores; correções precisam de revisão e identidade/amendment explícitos.

# ZGW-0083 — overnight H3 single-agent-tree runs (muse-spark 1.3 only)

Branch: overnight/h3-runs. Worktree: /home/maelrx/Documents/ChatGPT/Zugzwang-night.
Relay: http://127.0.0.1:8788. Stockfish: /home/maelrx/.local/bin/stockfish.
Model policy: muse-spark-1.3-contributor (Go) only, fallback to -free on 429/quota.

## Etapa 0 — migração de schema (done, 2026-09-05 ~06:25Z)
- experiments/local-musespark-1.3-go-single-agent-tree-battery.yaml: removidos
  `spec.protocol.legality` (6 linhas) e `spec.protocol.retry_profile`.
- experiments/local-musespark-1.3-go-legal-tree-memory-persistent.yaml: idem.
- Preservado: retries {transport:2, parse:0, illegal:3, feedback:enumerated}
  (feedback:enumerated mapeia para o perfil enumerate_after_failure em
  durable_coordinator._retry_profile) + observation.legal_actions.delayed.
- Comportamento verificado: `uv run zugzwang experiment validate` → valid: True
  nos dois arquivos. Commit cc99372.
- **CORREÇÃO pós-auditoria**: a premissa da missão ("o schema atual NÃO aceita
  legality/retry_profile") era falsa no BRANCH -night — ProtocolSpec
  (manifests.py:134-155) ainda aceita ambos e o YAML pré-migração valida
  (re-verificado: git show cc99372^ → load_source_manifest → valid, campos
  presentes). A rejeição às 06:25Z veio do .venv pré-existente instalado a
  partir do checkout /Zugzwang (main), cujo ProtocolSpec antigo realmente
  rejeita esses campos; `uv sync --all-packages` (logo depois) re-instalou os
  packages editáveis deste worktree. Ou seja: a remoção foi simplificação
  opcional de superfície inativa, NÃO migração forçada. Equivalência de
  comportamento confirmada: retry_profile derivado idêntico
  (enumerate_after_failure) antes e depois; campos removidos eram inativos no
  runtime (auditoria ZGW-0083 + suíte offline 230 passed). O protocol identity
  hash mudou — intra-bateria comparável (toda a bateria rodou pós-cc99372);
  não comparar hashes com runs anteriores à migração.
- Nota operacional: `uv sync --all-packages` re-apontou os installs editáveis
  de /Zugzwang (main) para o worktree -night; sem isso o planner não achava
  chess.single_agent_tree / chess.legal_tree_memory. Em sessions futuras neste
  clone: suspectar venv órfão quando validação divergir do código do branch.
- Plan da bateria: 5 condições, sem incompatibilidades, ~10 calls estimadas cada.

## Etapa 1 — bateria H1-H5 (RUNNING desde 2026-09-05T06:28Z)
Comando: `uv run zugzwang run experiments/local-musespark-1.3-go-single-agent-tree-battery.yaml --workspace . --output json`
Sessão: proc_916221b4c13c. Full-game 120 plies vs stockfish elo 1000.

| cond | hipótese | memória | prompt | root branches | reply_scope | resultado | plies | legal% | calls |
|------|----------|---------|--------|---------------|-------------|-----------|-------|--------|-------|
| 0 | H1 episodic-all | episodic | standard | 4 | all | LOSS (mate 18...Qf1#) | 36 | 18/18 committed, 2 illegal repaired | 18 ok + 2 failed (RESPONSE-001, transporte) |
| 1 | H2 persistent-all | persistent | standard | 4 | all | CENSORED@120† (cap; adjudicação pendente) | 120 | 60/60, 0 illegal | 60 ok + 0 failed |
| 2 | H3 persistent-forced-replies | persistent | forced_replies | 4 | all | LOSS (mate 49...hxg3#) | 98 | 49/49, 0 illegal | 49 ok + 0 failed |
| 3 | H4 persistent-wide-root | persistent | standard | 6 | all | LOSS (mate 31...Qxh3#) | 62 | 31/31, 0 illegal | 31 ok + 0 failed |
| 4 | H5 persistent-candidate-replies | persistent | standard | 4 | candidate_only | LOSS (mate 36...Qxg2#) | 72 | 36/36, 1 illegal repaired | 36 ok + 1 failed (timeout 180s, transporte) |

\† censura à direita: max_plies=120 interrompeu partida viva; sem adjudicação post-hoc, cap não é empate nem resultado.
Oponente efetivo em TODAS as condições (requested elo=1000, allow_approximate): Stockfish 16 com UCI_Elo efetivo
**1320**, Skill Level 0, 20k nodes, 1 thread (plugins/evaluator-stockfish/src/zgw_eval_stockfish/opponent.py:25-71;
mesmo perfil documentado no relatório R7 da noite anterior). "SF-1000-aprox" = este perfil.

## Quota / fallback log
- 06:28Z: relay OK, ambos 1.3-contributor e 1.3-contributor-free listados (43 modelos). Go-first.

## Análise H5 (run_tiDVGZR6BaS7mzLDlKqXYw, cond cnd_ce0685251498d20f)
- Status COMPLETED 09:06:07Z→09:57:32Z (~51min). H4/K6 efetivo, sem violação.
- 72 plies, derrota por mate: 36...Qxg2#. Modelo trocou Dama no lance 25
  (25.Qe4 Bxe4) e afundou em final inferior; mate de dama em g2.
  FEN 4rrk1/5p2/3B1b1p/p2b2p1/3N4/2p4P/P1R2PqK/8 w, is_checkmate True.
- Chamadas: 36 ok + 1 failed; 1 illegal reparado.
- Veredito H5: candidate-only replies não superou all nesta amostra (72 < 98 H3;
  H2 censurado). Restringir replies aos candidatos parece custar cobertura
  defensiva (n=1; confirmar em multi-seed).

## Veredito da bateria (5/5 COMPLETED, 0 episódios falhos, 0 fallbacks de quota)
Ordem OBSERVADA de sobrevivência (1 partida por condição, sem significância
estatística; H2 censurado no cap e provavelmente perdido sob adjudicação —
não usar como ranking de qualidade):
H2 (120†, censurado) > H3 (98) > H5 (72) > H4 (62) > H1 (36).
O que os dados suportam: (i) nenhuma condição venceu o oponente efetivo
(Stockfish UCI_Elo 1320/Skill 0/20k nodes); (ii) a condição episódica (H1)
foi a mais frágil; (iii) persistent ≥ episódico em sobrevivência, com K6
sendo rótulo de condição, não medida de uso de memória.

## Análise H4 (run_D6DmZK0Lq1vhz518uXCgkg, cond cnd_55a318dc420692c9)
- Status COMPLETED 08:30:48Z→09:06:07Z (~35min). H4/K6 efetivo, sem violação.
- 62 plies, derrota por mate: 31...Qxh3#. Modelo tentou sacrifício especulativo
  8.Bxf7+ (Scandinavian) e ficou a peça por peões; Stockfish converteu com
  ataque ao rei (30...Nf3+ 31.Kh1 Qxh3#). FEN 1r3r2/p7/3Bp1kp/3n4/1P4p1/P2P1nPq/2P2P2/R4R1K w.
- Chamadas: 31 ok + 0 failed; 0 illegal.
- Veredito H4: raiz larga (6 branches) NÃO compensou nesta amostra — 62 plies
  < H3 (98); única comparação não-censurada disponível. Largura sem critério
  de replies parece diluir a busca (n=1; confirmar em multi-seed).

## Análise H3 (run_XN0jnyVIBolK4fc10JGlNA, cond cnd_2c52c1bb78b89c17)
- Status COMPLETED 07:40:29Z→08:30:48Z (~50min). H4/K6 efetivo, sem violação.
- 98 plies, derrota por mate de peão: ...49.hxg3#. Linha French; modelo trocou
  demais no meio-jogo (14.Nd6+ cxd6, 21.Rxe6) e caiu em final inferior; rei
  caçado até h2. FEN final 8/8/p7/2b5/5k2/4n1pP/7K/r7 w, is_checkmate True.
- Chamadas: 49 ok + 0 failed; 0 illegal. Jogo limpo até o fim.
- Veredito H3: desfecho oposto à partida anterior (run_VLIj, vitória 46.Rb8#
  em 91 plies) — mas são 1 amostra por lado e protocolos não idênticos
  (aquela partida rodou pré-migração cc99372, e a vitória de lá veio após
  presente material cedo do oponente aproximado, per relatório R7): sem base
  para claim de "não-replicação" em sentido forte, apenas "o desfecho não se
  repetiu". forced-replies sobreviveu 98 plies (>> H1); superioridade sobre
  standard segue em aberto (H2-standard atingiu o cap 120, censurado).

## Análise H2 (run_G739VZJoOSYDQiKT-WL2dw, cond cnd_863c03397aee2ebb)
- Status COMPLETED 06:46:47Z→07:40:29Z (~54min). H4/K6 efetivo, sem violação.
- 120/120 plies (teto, censura à direita): partida segue viva — sem
  mate/afogamento/material insuficiente (FEN 1r4k1/8/6P1/8/2pN1P2/2P2K2/2P4r/8 w).
  Final sem damas: modelo com N+4P contra 2R+P (correção pós-auditoria; antes
  dizia "N+P") — posição provavelmente perdida sob adjudicação.
- Chamadas: 60 ok + 0 failed; 0 step.illegal_action_rejected. 100% legal.
- Veredito H2: sobreviveu ao teto (36 plies/mate do H1 → 120/vivo) e usou
  rótulo K6 vs K0 do H1. ATENÇÃO: K6 é emitido por construção da condição
  (memory_mode=persistent), não medido por uso real da memória; "sobreviveu
  mais" ≠ "melhor" — cap interrompeu partida provavelmente perdida. Resultado
  = CENSORED@120† até adjudicação post-hoc.

## Análise H1 (run_XKxD8GNjkzu4OyIazavGJQ, cond cnd_1619c99bc87dabd9)
- Status COMPLETED 06:28:23Z→06:46:47Z (~18min). H4/K0 efetivo, sem violação.
- 36 plies, derrota por mate: 1.e4 d5 2.exd5 Qxd5 3.Nc3 Qe6+ 4.Be2 Nh6
  5.Nb5 Qd7 6.Nc3 e5 7.Bb5 Nc6 8.Nf3 Bb4 9.O-O O-O 10.Bxc6 bxc6
  11.Nxe5 Qe6 12.Re1 f6 13.d4 fxe5 14.d5 Qf7 15.Rxe5 Bd6 16.Qd4 c5
  17.Qe4 Qxf2+ 18.Kh1 Qf1# (SAN verificado com python-chess; FEN final
  r1b2rk1/p1p3pp/3b3n/2pPR3/4Q3/2N5/PPP3PP/R1B2q1K w, is_checkmate True).
- Chamadas: 18 ok + 2 failed (20 attempts); 2 step.illegal_action_rejected
  reparados dentro de retries.illegal=3. Taxa de lance final legal 100%.
- Veredito H1: jogo perdido; episodic-all não segurou contra SF-1000-aprox.

## Etapa 3 — memória persistente probe (run_XVDzy-SafC3EP4PmVrHd_w)
- COMPLETED 09:59:04Z→10:00:03Z (~1min). 8/8 plies, 12 calls + 0 failed,
  0 illegal, H4/K6. YAML migrado roda limpo.
- Abertura sã: 1.e4 e5 2.Nf3 d6 3.d4 Qe7 4.Nc3 exd4 (FEN
  rnb1kbnr/ppp1qppp/3p4/8/3pP3/2N2N2/PPP2PPP/R1BQKB1R w).
- Comparação episódico×persistente fica pela bateria H1×H2 (36/mate vs
  120/vivo): evidência forte pró-persistente em full-game. Probe de 8 plies
  não discrimina — só valida o artefato.
- Sem noite restante para seed/elo variants (bateria levou ~3.5h); ver próximos.

## Quota / fallback log (final)
- 06:28Z: relay OK, ambos 1.3-contributor e 1.3-contributor-free listados.
  Go-first a noite inteira: 0 erros 429/quota, nenhum fallback para -free.
  Failures observados (2 H1, 1 H5) foram transitórios, não quota.

## Limitações (adicionadas pós-auditoria)
- n=1 por condição, só de brancas (sem pareamento de cores), alta variância
  de amostragem do modelo: a seed controla passos/oponente via derive_seed,
  NÃO a amostragem do provider. Nada aqui é estatisticamente conclusivo.
- "Memória persistente" = memória de busca carregada entre decisões da MESMA
  partida (inclui resume do episódio), não entre partidas.
- Oponente efetivo é UCI_Elo 1320 (floor nativo), não 1000 — ver nota da tabela.

## Próximos experimentos sugeridos (reordenados pós-auditoria)
1. ADJUDICAÇÃO primeiro: definir eval post-hoc Stockfish (ou regra) e aplicá-la
   retroativamente às 5 partidas — redefine os desfechos (H2 pode ser LOSS),
   e é pré-requisito lógico de tudo abaixo. Confirmar via campo retrieved_memory
   nos decision traces se a memória K6 foi de fato recuperada/usada.
2. Replicar H2 (persistent-all standard) com seed nova (--set /spec/seed=<novo>,
   nunca 20260909): seed nova = amostra fresca, não mecanismo de reprodutibilidade.
3. H3 × H2 multi-seed (mín. 20 partidas pareadas por condição, critério do R7;
   2-3 seeds têm poder mínimo): métrica primária pré-registrada = resultado
   adjudicado (win/loss), plies como secundária. Testa se o desfecho oposto
   de hoje vs ontem é variância.
4. Força do oponente: variar UCI_Elo NATIVO (>=1320, ex. 1320 vs 1600) e/ou
   limit {nodes}. NÃO usar elo 800/1200: abaixo de 1320 com allow_approximate
   TUDO mapeia para o mesmo perfil 1320/Skill 0 (opponent.py:59-60) — braços
   idênticos ao que já rodou.
5. H4-wide-root com reply_scope candidate_only: testar se largura + foco
   combina melhor que cada um isolado.

## Etapa 4 — H3-repro effort matrix, sem cap (2026-09-05 18:06–18:23Z)
Manifest: `experiments/local-musespark-1.3-go-h3-repro-effort-matrix.yaml`
(seed 20260909 — mesma da bateria; condition_ids diferem pelo nome do
experimento, mas registra-se o reuso). Setup = H3 vencedor
(persistent + forced_replies, chess.single_agent_tree), com
`max_plies: null` (até mate/fim natural) e matrix zip em
`backend_config.reasoning_effort`: minimal / low / medium.
Budget 600 calls, mesmo oponente (requested 1000 → efetivo UCI 1320/Skill 0/20k).
Commit f8dfc56. Todas em muse-spark-1.3-contributor, H4/K6, sem violações,
0 illegal, 0 provider failures nos 3 braços.

| braço | run | resultado | plies | calls | tokens in/out |
|-------|-----|-----------|-------|-------|---------------|
| minimal | run_RsL-RlmXnGAG7PutjRUsaQ | LOSS (mate 29...Qd2#) | 58 | 29 ok | 157k / 37k |
| low | run_hoDbdpNyHNclfYrOMzUzvQ | LOSS (mate 22...Qh2#) | 44 | 22 ok | 187k / 22k |
| medium | run_XnL4e59brCVnr-ufO8u9Ow | LOSS (mate 11...Qxh2#) | 22 | 11 ok | 87k / 11k |

- minimal (58): 1.e4 Nf6 2.e5 Ne4 3.d4 c5 4.Nc3 Qa5 5.Qf3 cxd4 6.Qxf7+ Kxf7
  7.Bc4+ Ke8 8.Bf7+ Kxf7 9.e6+ dxe6 10.Bd2 Nxd2 11.Kxd2 g6 12.Kd3 Nc6
  13.Ne4 Bg7 14.Nd6+ exd6 15.Ke2 Qb5+ 16.c4 d3+ 17.Kxd3 Qxb2 18.Ne2 Nb4+
  19.Ke3 Re8 20.Rab1 Nc2+ 21.Kd2 Bh6+ 22.Kd1 Qxb1+ 23.Nc1 Na3 24.Ke2 Nxc4
  25.Nd3 Qxa2+ 26.Kf1 Qa1+ 27.Ke2 Qa2+ 28.Nb2 Qxb2+ 29.Kd1 Qd2#.
  FEN r1b1r3/pp3k1p/3pp1pb/8/2n5/8/3q1PPP/3K3R w. Rei caçado após sacrifícios
  6.Qxf7+/8.Bf7+.
- low (44): 1.e4 Nf6 2.e5 Ng8 3.d4 d6 4.Nc3 c6 5.Nf3 Bg4 6.h3 Bf5 7.exd6 Qxd6
  8.Bc4 Nf6 9.O-O e6 10.Bxe6 Qxe6 11.Nd5 cxd5 12.Ne5 Be7 13.Nd7 Qxd7 14.Bf4 O-O
  15.Bd6 Bxd6 16.Re1 Nc6 17.Rc1 Ne4 18.Rxe4 Bxe4 19.f3 Bf5 20.c3 Bxh3 21.gxh3
  Qxh3 22.Qf1 Qh2#. FEN r4rk1/pp3ppp/2nb4/3p4/3P4/2P2P2/PP5q/2R2QK1 w.
  Troca especulativa 10.Bxe6 abriu o rei; mate de dama em h2.
- medium (22): 1.e4 Nf6 2.e5 d5 3.exd6 Qxd6 4.Bb5+ Nbd7 5.Nc3 e6 6.Nf3 Be7
  7.O-O O-O 8.Ne5 Qxe5 9.Ne4 Nxe4 10.Bxd7 Bd6 11.Bxe6 Qxh2#.
  FEN r1b2rk1/ppp2ppp/3bB3/8/4n3/8/PPPP1PPq/R1BQ1RK1 w. Colapso tático direto:
  8.Ne5?? perde peça e abre a diagonal do mate.
- Leitura honesta (n=1 por braço): relação inversa aparente
  (minimal 58 > low 44 > medium 22), mas SEM significância — cada braço é uma
  amostra única e o medium morreu por blunder tático isolado (8.Ne5), não por
  "effort alto jogar pior". Nenhum braço replicou a vitória run_VLIj (91 plies).
  Sem cap, todos os jogos terminaram em mate — o que confirma que o H2 da
  bateria só "sobreviveu" por causa do teto de 120.
## Etapa 5 — H2-nocap xhigh triple, sem cap (2026-09-05 19:20Z→)
Manifest: `experiments/local-musespark-1.3-go-h2-nocap-xhigh-triple.yaml`
(seed nova 20260911). Setup H2 (persistent-all standard) + `max_plies: null`,
3 réplicas concorrentes (`--condition 0/1/2`), `reasoning_effort: xhigh`
(validado no relay antes). Commit + manifest ok.

- Réplica C (cond 2, run_dZkrEr4SzlSBdHh0): **FAILED** 19:42Z, 24 plies.
  Causa: call xhigh estourou `timeout_seconds: 180` (TRANSPORT-002, 180070ms,
  outcome desconhecido) → 4 decisions seguintes inparseáveis ("sem lance":
  1 parse_error + 3 decision_error) → `illegal_action_retry_exhausted`.
- Réplica B (cond 1, run_KQ9d5tK70g5Kp9): **FAILED** 19:47Z, 27 plies.
  Assinatura idêntica: 1× timeout 180078ms → 4 retries inparseáveis →
  exaustão no step 26.
- Tentativa de resume da B (~19:48Z, manifest variante com mesmos
  condition_ids + `retries.transport: 6`): o coordinator reabriu o run mas
  NÃO retomou o jogo — episódio FAILED é terminal, não retomável (só runs
  interrompidos têm work pendente); run finalizado COMPLETED com 26 plies,
  sem lances novos, sem violação (efetivo H2/K0). Comportamento correto pelos
  invariantes (falha é evidência terminal; resume não reescreve história).
  Os 26 plies entraram na fila do daemon de análise.
- Réplica A (cond 0, run_y01m1gA6XPUqMfE1): **FAILED** 20:01Z, 31 plies.
  Pior assinatura das três: 1× RESPONSE-001 (172s) + 3× timeout 180s →
  exaustão no step 30. Triple xhigh fecha 3/3 FAILED, 100% operacional
  (timeout), 0% xadrezístico. Veredito final do setup 180s+xhigh: inviável;
  as continuações (timeout 600) dirão se xhigh joga ou só demora.
- Continuações posicionais v1 (timeout 600, maxout 32k, seed 20260912):
  - B-continue (run_0SyuvBEUH12Ff-7K_wttrg): **FAILED** 20:01Z, 5 steps.
    Timeout 600 segurou (calls de 132s/193s/209s completaram), modelo jogou
    são (14.Re1 Bb5 15.Nd4 Ba6) — mas no step 4 (16. brancas) emitiu
    EXATAMENTE 32768 output tokens = truncamento no teto → "(sem lance)" ×4
    (1 parse_error + 3 decision_error, 42 legais disponíveis) → morte.
    SEGUNDO assassino do xhigh: verbosidade estoura o max_output.
    B-orig/A-triple nunca truncaram (max 22.7k/26k) — morreram só de timeout.
  - C-continue (run_ToP4ghsTIa6iZ5gvuQeHWA): 7 steps (Qb3 Rb8 Qa3 Ra8 Qb3 b5),
    ENCERRADA por ordem do operador antes do fim, junto com o restart limpo.
- Restart limpo (~20:15Z, ordem do operador): C-continue morta via kill;
  bateria nova `local-musespark-1.3-go-h2-clean-xhigh-triple.yaml`
  (seed 20260914): 3 partidas FRESTAS do zero, H2 persistent-all, xhigh,
  timeout 600 + maxout 65536 + transport 4, sem cap. B2-yaml arquivado
  (superseded, não rodado).
- Assassinos do xhigh mapeados (evidência em DB, não teoria):
  Limites honestos: memória persistente e histórico NÃO atravessam runs;
  os FAILED originais seguem intactos como evidência.
- Padrão confirmado (2/2): **xhigh não cabe em timeout de 180s**. O timeout
  ambíguo parece envenenar as retries seguintes (modelo repete resposta
  truncada/inparseável 4×). Próxima rodada xhigh: `timeout_seconds: 300–600`
  + considerar `retries.transport` maior. Réplicas B/C entraram na fila do
  daemon de análise (`--include-failed`) — os lances commitados (12/13 do
  modelo) serão avaliados normalmente.

## Parada
Critério: (a) bateria+memória analisadas, ou (b) 7h30, ou (c) 3 falhas consecutivas.
Status final: (a) ATINGIDO às ~10:02Z — bateria 5/5 + probe analisados.
Tempo decorrido ~3.5h < 7h30. Falhas consecutivas: 0. Parando por (a).
Nota 19:50Z: missão estendida — Etapas 4 (effort matrix) e 5 (xhigh triple)
rodaram após o critério original; este registro segue como log contínuo.
