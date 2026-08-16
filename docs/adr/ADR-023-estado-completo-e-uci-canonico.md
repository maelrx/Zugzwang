---
id: ADR-023
title: "Estado completo e UCI canônico"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-023: Estado completo e UCI canônico


**Status recomendado:** aceitar.  
**Decisão:** persistir full game state/history; ação UCI.

### Opções

1. FEN apenas.
2. PGN/SAN como verdade.
3. structured state + history e UCI action.

### Trade-offs

FEN perde repetição/história. SAN é contextual e carrega pistas. UCI é mecânico, mas menos familiar ao modelo; isso é exatamente uma variável de observation, não razão para contaminar storage.

### Impactos

- **Direto:** codecs e history tracking.
- **Indireto:** replay correto, rare rules e transforms.
- **Exterior:** interoperabilidade com engines e datasets.
- **Subjetivo:** diferencia estado científico de representação exibida.

### Reversibilidade

Alta. Mudar action identity quebra bundles e metrics.

### Reavaliar quando

Variantes exigirem action schema mais amplo; versionar, não reinterpretar UCI antigo.

---
