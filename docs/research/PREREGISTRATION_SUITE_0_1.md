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
- Modelos: `opencode-go/deepseek-v4-flash` (texto) e `opencode-go/gpt-5.6-luna`
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
