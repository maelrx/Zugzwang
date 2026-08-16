# Especificação do corpus de avaliação v0.1

Este documento define a forma do primeiro corpus, não entrega as posições. A amostra final só é congelada em M6 depois de auditoria de licença, contaminação e difficulty calibration.

## Objetivo

Suportar comparações pareadas de representação, grounding, knowledge packets, multimodalidade e demonstrations sem permitir que uma única distribuição domine o resultado.

## Unidade canônica

```text
PositionFamily
├── canonical chess state
├── source/provenance
├── temporal metadata
├── phase/structure/tactical labels
├── legal actions hash
├── engine-evaluation snapshot
├── representation artifacts
└── optional metamorphic siblings
```

A unidade de split e bootstrap é `PositionFamily`, nunca um prompt renderizado.

## Composição piloto sugerida

| Slice | Piloto | Confirmatório inicial | Função |
|---|---:|---:|---|
| Human IID held-out | 120 | 800 | comparabilidade com uso real |
| Temporal post-cutoff | 80 | 400 | reduzir contaminação |
| Random-legal | 80 | 400 | tracking/rules OOD |
| Geometric/metamorphic | 60 families | 300 families | equivariância |
| Rare rules | 40 | 160 | castling/en passant/promotion/repetition |
| Synthetic impossible | 40 | 160 | abstention/state validation |
| Tactical puzzles | 80 | 400 | cálculo local por motif/depth |
| Quiet strategic | 80 | 400 | value/knowledge packet effects |

Os números confirmatórios são proposta para power planning, não compromisso. O custo e a variância observada no piloto determinam a amostra final antes da preregistration.

## Balanceamento

- side to move;
- phase;
- material bucket;
- evaluation bucket;
- tacticality;
- legal branching factor;
- opening-family familiarity;
- forced versus multiple-good-move positions;
- visual density/occlusion proxies;
- knowledge-packet applicability.

## Origem permitida

- Lichess/open corpora sob licença compatível;
- games posteriores ao cutoff quando disponíveis;
- engine self-play generated after cutoff;
- random-legal trajectories;
- programmatically transformed states;
- purpose-built rare-rule fixtures.

Cada row mantém source license and derivation chain. Posição pública não é assumida livre de contaminação.

## Exclusions

- target move presente em prompt/metadata;
- transposição próxima encontrada no knowledge/demo corpus;
- posição inválida fora da suite impossible-state;
- engine disagreement instável sob o budget escolhido;
- duplicate/transposition leakage entre split families;
- unclear redistribution rights para public bundle.

## Frozen artifacts

- corpus manifest and SHA-256;
- canonical states;
- source references;
- split assignments;
- render configs and image hashes;
- evaluator version/config;
- condition-applicability map;
- exclusions with reason codes.

## Hidden test policy

Uma parte do corpus pode permanecer privada para reduzir adaptive overfitting. O public report precisa declarar tamanho, geração, governance e quem teve acesso, sem revelar os itens antes da avaliação quando isso destruir o objetivo.
