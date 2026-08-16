# Experiment Card — Research Suite 0.1 (ZGW-0076)

## Identidade

- **Suite**: `research-suite-0.1` (14 condições, 10 posições congeladas)
- **Preregistration**: `docs/research/PREREGISTRATION_SUITE_0_1.md` (mesma data)
- **Corpus**: `datasets/positions_v1/positions.yaml` — sha256 `1cd648063815deab6f0aa76d49f9fc14f8e49de68203b0efd781e592fe2154b7`
- **Status**: pilot-ready; execução paga pendente de ratificação GATE-011

## Condições (14)

| Bloco | Condição | Manifest | Modelo | Protocolo |
|---|---|---|---|---|
| REP-001 | FEN | `rep-001-fen.yaml` | deepseek-v4-flash | R0/H2/K0, fen |
| REP-001 | PGN | `rep-001-pgn.yaml` | deepseek-v4-flash | R0/H2/K0, history full san |
| REP-001 | RGB | `rep-001-rgb.yaml` | mimo-v2.5 | R0/H2/K0, image only |
| REP-001 | FEN+RGB | `rep-001-fen-rgb.yaml` | mimo-v2.5 | R0/H2/K0, fen+image |
| GROUND-001 | free (G0) | `ground-001-free.yaml` | deepseek-v4-flash | R0/H2/K0, livre UCI |
| GROUND-001 | legal-first (G2) | `ground-001-legal-first.yaml` | deepseek-v4-flash | R1/H3/K0, legal always |
| GROUND-001 | reason-first (G4) | `ground-001-reason-first.yaml` | deepseek-v4-flash | R1/H3/K0, delayed 2 fases |
| SKILL-001 | baseline (S0) | `skill-001-baseline.yaml` | deepseek-v4-flash | R0/H2/K0 |
| SKILL-001 | persona (S1) | `skill-001-persona.yaml` | deepseek-v4-flash | R0/H2/K1, prompt hook |
| SKILL-001 | correct (S4) | `skill-001-correct.yaml` | deepseek-v4-flash | R0/H2/K4, packet najdorf |
| SKILL-001 | wrong (S5) | `skill-001-wrong.yaml` | deepseek-v4-flash | R0/H2/K4, packet KID |
| SKILL-001 | irrelevant (S6) | `skill-001-irrelevant.yaml` | deepseek-v4-flash | R0/H2/K1, token-matched |
| MM-002 | consistent | `mm-002-consistent.yaml` | mimo-v2.5 | fen+image idênticos |
| MM-002 | conflict | `mm-002-conflict.yaml` | mimo-v2.5 | fen ≠ image (1 peça), authority=text |

## Hipóteses (resumo; detalhe na preregistration)

- **H1 (REP)**: com estado simbólico perfeito, RGB redundante não melhora a
  qualidade de decisão além do ruído (scaffold espacial pode existir sem ganho).
- **H2 (GROUND)**: reason-first (G4) difere de legal-first (G2) na distribuição
  de candidatos e em parse/legal-rate, a custo de 1 call extra.
- **H3 (SKILL, assinatura)**: `S4 > S0` **e** `S4 >> S5 ≈ S6` (conteúdo causal,
  não esforço textual).
- **H4 (MM-002)**: com `modality_authority: text`, o conflito de uma peça
  degrada menos que sem autoridade declarada (probe de trust por modalidade).

## Métricas primárias

- `chess.cpl`, `chess.move_class`, `chess.best_move_agreement` (Stockfish 18 pós-hoc, GATE-006)
- parse/legal/illegal rate, tokens, latência, `effective_assistance` H/K por episódio
- probe: state reconstruction opcional (subconjunto) para decompor percepção vs política

## Orçamento piloto (referência)

- 14 condições × 10 posições × (1–2 calls) ≈ 210 calls; deepseek-v4-flash e
  mimo-v2.5 via assinatura OpenCode Go (sem custo marginal extra).
- Stockfish 18 local, 20k nodes por posição.

## Limitações declaradas

1. **Modelo × condição é confundido** para RGB: texto usa deepseek-v4-flash,
   imagem usa mimo-v2.5. Análise por bloco/condição, não ranking entre modelos.
2. Budget pareado em calls, não em tokens de imagem (tokenização visual varia).
3. Single-move selection; nenhum claim de Elo nem full-game neste batch.
4. GATE-011 pendente: execução completa paga só após ratificação do operador.

## Promotion gates (batch 1 → batch 2)

- Condição só sobe para full-game se: efeito observado > mínimo prático
  (ACPL médio) E custo por observação dentro do orçamento E atribuição H/K íntegra.
