# Preregistration — Research Suite 0.1

**Date**: 2026-08-16
**Suite**: `experiments/research-suite-0.1/` (14 manifests)
**Corpus**: `datasets/positions_v1/positions.yaml` v1.0.0
  (sha256 `1cd648063815deab6f0aa76d49f9fc14f8e49de68203b0efd781e592fe2154b7`)
**Protocol coordinates**: `zgw.dev/v1alpha1`; H/K declarados por condição;
efetivo auditado por episódio; prompt/packets/observação entram no protocol hash.

## Design

- Posições congeladas: 10 (opening 2, middlegame 4 [2 quiet/2 tactical],
  endgame 2, OOD 2). Cada condição roda TODAS as posições (within-subject).
- Cada posição é um run independente; ação = 1 move-selection call
  (2 calls na condição G4). Stockfish 18 avalia pós-hoc (H5+ apenas na avaliação,
  nunca na decisão; GATE-006).
- Modelos: `opencode-go/deepseek-v4-flash` (texto) e `opencode-go/mimo-v2.5`
  (imagem) — assinatura do operador; ratificação formal em GATE-011.

## Hypotheses (preregistered)

- **H1 (REP-001)**: `FEN ≥ PGN` em qualidade média (estado simbólico direto);
  `FEN+RGB ≈ FEN` (imagem redundante não adiciona competência ao estado perfeito).
- **H2 (GROUND-001)**: `legal-first` maximiza legal-rate; `reason-first`
  produz candidatos diferentes e legal-rate ≥ free, com 2x calls.
- **H3 (SKILL-001, assinatura)**: `S4 > S0` e `S4 > S5` e `S5 ≈ S6` (conteúdo
  causal > esforço textual). Susceptibilidade reportada se S5 < S0.
- **H4 (MM-002)**: conflito de uma peça degrada CPL médio; `modality_authority:
  text` mitiga parcialmente. Trust por modalidade derivado da mudança.

## Analysis plan

1. Por condição: ACPL médio, % best_or_good, legal/parse rate, tokens, latência.
2. Contrastes pareados por posição (same position, across conditions):
   - FEN vs PGN vs RGB vs FEN+RGB;
   - free vs legal-first vs reason-first;
   - S0 vs S4 vs S5 vs S6 (S5 vs S6 = controle de token-matching);
   - MM consistent vs conflict.
3. Sem p-hacking: todos os contrastes pré-especificados acima; nada de
   selecionar posições post-hoc. Análises exploratórias rotuladas como tal.
4. Poder: n=10 por condição é piloto de efeito grande; full batch (n≥24)
   só após GATE-011.

## Stop conditions

- Qualquer run com assistência efetiva > declarada ⇒ suite pausada e auditoria
  (`audit-assistance-provenance`).
- Custo exceder 2x o piloto estimado sem ratificação ⇒ pausa.
- Modelo de visão incapaz de jogar lance legal > 50% no MM-consistent ⇒ bloco
  MM marcado inválido para esse modelo (não força conclusão).

## Amendment policy

Mudanças pós-preregistration exigem card revision v2 e registro no
`DECISION_LOG.md` antes de re-executar.

## Amendment 001 — 2026-09-06 (ZGW-0085, issue #14)

Registrado ANTES de qualquer execução paga da suite (GATE-011 segue pendente).
Runs overnight já executados permanecem evidência exploratória n=1; nenhum
manifesto congelado foi reescrito. Correções e esclarecimentos:

1. **rep-001-pgn**: a condição parte de FEN sem trajetória prévia e produz
   histórico vazio — não compara "PGN vs FEN" como preregistrado. Fica
   reclassificada como réplica de FEN com prompt de histórico; a hipótese H1
   (FEN ≥ PGN) só é testável com corpus de posições com histórico real
   (batch 2).
2. **rep-001-rgb / rep-001-fen-rgb**: modelo × condição permanece confundido
   (texto=deepseek-v4-flash, imagem=mimo-v2.5). Análise intrabloco com
   pareamento por posição e denominadores por condição; sem ranking entre
   modelos. Alternativa de modelo para RGB é decisão separada do operador.
3. **MM-002**: consistent vs conflict altera simultaneamente o conflito
   fen-image e a instrução de autoridade (`modality_authority: text`).
   O efeito da autoridade é reportado separadamente do efeito do conflito,
   com condição adicional de conflito sem override planejada para batch 2.
4. **SKILL-001**: o packet Najdorf (S4) não é controle de conhecimento
   pertinente para todas as 10 posições (ex.: finais P07/P08). Relevância
   por posição passa a ser reportada (nº de posições da casa do packet),
   e a comparação S4>S5 usa apenas posições da mesma estrutura.
5. **Bateria single-agent (H1–H5)**: os nomes de hipótese não substituem
   classes H/K. Mapeamento explícito — H1/H2/H3: R7/H4 (K0 episódica, K6
   persistente, K6 persistente + checklist); H4: R7/H4 com largura de raiz
   controlada; H5: R7/H4 com materialização pós-seleção. Correções de
   mecanismo (max_root_branches ativo no escopo `all`; rótulo
   root_affordance_timing; memory_summary com disponibilidade e relevância
   separadas) têm prova offline em tests/integration/test_single_agent_tree.py.
6. **Análise pareada**: toda comparação usa pareamento por pair_id com
   denominadores explícitos (n por condição, exclusões listadas) e
   agrupamento por posição-base; sem pooling de condições com modelos
   distintos.

## Amendment 002 — 2026-09-06 (GATE-011 ratificado, ZGW-0086)

Registrado ANTES de qualquer execução paga (nenhum run pago da suite existe).

1. **Matriz de modelos ratificada pelo operador** (GATE-011 → accepted): todas
   as 14 condições passam a usar um único modelo, `muse-spark-1.3-contributor`
   (plano Go via router opencode local `127.0.0.1:8788`, perfil
   `openai-responses`), com `muse-spark-1.3-free` como substituto manual do
   campo `model` quando a cota Go/free esgotar. `deepseek-v4-flash` e
   `mimo-v2.5` saem da matriz.
2. **Efeito sobre a Emenda 001:** com texto e visão no mesmo modelo, o
   confundimento modelo×condição do bloco RGB deixa de existir. As comparações
   REP-001 (FEN vs PGN vs RGB vs FEN+RGB) e MM-002 passam a ser intra-modelo.
3. **Manifests regenerados** pelo `generate_manifests.py` com corpus
   `positions_v1_1` (1.1.0, corrigido pela ZGW-0085). Os hashes de protocolo
   das condições mudam em relação aos manifests pré-emenda — os antigos
   permanecem no histórico como evidência do preregistro original.
4. **Orçamento:** cota da assinatura free+Go do operador; ~210 calls no piloto
   n=10; full batch n>=24 só após análise do piloto. Sem claims em USD
   (GATE-009 pendente); usage/tokens gravados com `cost_status=unknown`.
5. **Default experimental de memória (diretiva do operador):** experimentos
   full-game passam a usar estratégias com memória persistente como default
   (`memory_mode: persistent` em `chess.single_agent_tree`), com base nos
   primeiros resultados positivos validados do projeto — vitória `46.Rb8#` no
   jogo H3, sobrevivência do H2 persistente e empate em 224 plies na
   condição `a` da triple limpa (ZGW-0083/0084). As condições move-selection
   da suite 0.1 não são afetadas (não usam memória).
6. Critérios de stop da preregistration original permanecem: assistência
   efetiva > declarada, custo > 2× o piloto, ou visão < 50% legal interrompem
   a execução para revisão.
