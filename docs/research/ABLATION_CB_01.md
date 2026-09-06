# Ablação CB-01 (preregistrada): memória ON vs OFF em decisões journaled

> **Status:** preregistro (plano antes da análise final). Nenhum claim de
> rating ou superioridade com piloto. Custo: unknown (GATE-009 pendente).

## Questão

A memória condicionada (CB-M2 snapshots elegíveis) muda a seleção do loop
de navegação vs o mesmo loop sem memória, em posições e splits idênticos?

## Condições congeladas (route freeze)

| Campo | Valor congelado |
|---|---|
| Posições | `datasets/positions_v1_1` (1.1.0, P01/P09 corrigidos) |
| Split | development apenas (test isolado, TEST-047) |
| Versões | perception `chess-perception/v0.1`, packet `zgw.position-packet/v1`, envelope `zgw.cognitive-tool-result/v1` |
| Rota | `fake-direct` (offline; sem provider) |
| Estratégia | `chess.cognitive_navigation` 0.1.0, max_rounds=4 |
| Condições | A=memory-OFF (recall vazio), B=memory-ON (snapshot selado elegível) |

## Conjuntos

Pares (posição, condição): cada posição roda nas duas condições com mesma
seed. Somente pares completos entram na análise (dados completos).

## Plano estatístico (antes da análise final)

1. Métrica primária por par: `selected_match` (1 se ambas selecionam o mesmo
   UCI, 0 caso contrário) + `ops_delta` (B−A em operações cobradas).
2. Perspectiva: métricas de avaliação sempre na perspectiva do lado a mover;
   scores de mate (`#`) NUNCA entram em média de CP — contam-se à parte
   (TEST-071).
3. Diferenças negativas preservadas com sinal; relatório mostra sinal
   explícito, sem `abs()` oculto (TEST-072).
4. Pareamento: mesmas posições/splits/versões/rota nos dois braços; pares
   quebrados são excluídos e contados (TEST-073).
5. Custo: trabalho formal pré-computado (operações lógicas journaled) entra
   no custo; custo monetário = unknown (TEST-074, GATE-009).
6. n é piloto (pequeno): relatar intervalos, não significância.

## Relatório-modelo

| Par | Posição | A (OFF) | B (ON) | match | ops Δ | custo Δ |
|---|---|---|---|---|---|---|
| … | … | … | … | … | … | unknown |

**Decisão:** com evidência, priorizar memória vs skills (próximo passo §38.12).
