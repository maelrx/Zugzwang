# Estudo de Correlação ZGX — todas as partidas, SF depth-20 uniforme

**Data:** 2026-09-09 · **Autor:** agente (diretiva Mestre Mael) · **Artefatos:** `out/zgx_full_correlation/`
**Método:** todas as partidas completas (e o snapshot do jogo em andamento) reanalisadas com Stockfish 16, **depth 20**, Threads=1, convenção de records idêntica ao watcher oficial (`cp_before/cp_after` mover-POV, `regret = cp_before − cp_after`, blunder ≥ 300 cp, mate clampado em ±10000, ACPL capado em 1000). Dataset único: `games_dataset.json`; análises por lance: `sf20/*.json`; metadados de setup: `games_meta.json`; scripts: `sf20_analyze.py`.

## 1. Correções de dados descobertas pelo estudo

- **luna-02 e luna-03 NÃO eram "sem resultado"** — os PGNs exportados em `out/luna_fullgames/` estavam truncados/velhos. Os jsonl ao vivo mostram: luna-02 perdeu por **mate em 58** (`58...Qxe1#`) e luna-03 perdeu por **mate em 76**. A bateria luna-v2 real é **1W–3L–1falha(de provider)**, não "quase vitórias".
- 6 jogos R1 (glm/opus/sonnet) tinham workspaces apagados de `/tmp`; PGNs reconstruídos dos records salvos e reanalisados.
- Os JSONs antigos usavam 3 formatos/agregados diferentes (e ACPL inflado por mate-score sem clamp — ex.: gemini-03 "5867"). Aqui tudo passou pelo mesmo método.

## 2. Corpus e placar (vs Stockfish 1320, 20k nós)

**21 partidas analisadas uniformemente** (13 full games R1 + 5 luna-v2 + 3 gemini-R2 + 1 muse-R2 snapshot de 104+ plies) + 5 de arena (vs humano, contexto à parte).

| Trilha | Placar decidido | Vitórias |
|---|---|---|
| Gemini R1 (r4, hist6) | 2W–3L | full-01 (mate 135), full-03 (mate 61) |
| Gemini R2 v2 (r6, inline, hist12) | **2W–1L** | tactical-memory-v2 (mate 83, **1 blunder**), tactical-guardian-v2 (mate 67, **1 blunder**) |
| Luna v2 (high) | 1W–3L | tactical-memory (mate 65, **0 blunders**) |
| Muse R1 (low) | 0W–3L | — |
| Muse R2 (medium, em andamento) | — | ply 104+, ACPL 46.9/1 blunder, mas eval −400…−520 (piora posicional) |
| GLM/Opus/Sonnet R1 | 0W (todos morreram ≤20 plies por provider/abort) | — |

**Total decidido: 5W–10L.** Modelos fora da via principal (GLM/Opus/Sonnet) não produzem sequer jogo completo — o gargalo atual é gemini/muse/luna.

## 3. Padrões correlacionados

### P1 — A qualidade é binária e vive no final do jogo
- Vitórias: ACPL do modelo 28–115; derrotas: 90–191. Na era r6, ganhar exigiu **≤1 blunder** e ACPL ≤ 42.5.
- Dos 75 blunders do modelo, **apenas 3 na abertura (nenhum ≥1000)**; erros fatais (≥1000): **27/40 no final**, 13 no meio-tardio.
- **6 das 10 derrotas = mate sofrido em 1–2 lances de posição já pior** (cegueira tática de 1 lance: muse-02 `Kg1??`, muse-03 `Rf2??`, luna-04 `Bf4??`→`Bh3#`, full-05 `Rxe7??`, luna-02 `Bxd7??`, luna-03 `Re2??`). Não é plano ruim — é não ver a resposta forçada.
- 3/10 = derrocada em cluster no final (rei passeando: `Kg2/Kh3/Kh4…`, full-04 com 16 blunders, gemini-02 com 12).

### P2 — Conversão é tudo ou nada
- Vantagem ≥ +300 foi alcançada 8 vezes: **5 convertidas, 3 desperdiçadas (lead protection 62,5%)**.
- Quem desperdiçou (full-02 peak +9995→Rc8??, full-05 +666→erro 5 plies depois, gemini-02 +407→erro no lance seguinte) cruzou o zero **em ≤4 plies após o primeiro erro pós-pico**.
- Quem converteu, converteu com mate 10–17 plies depois do último erro do 1320 — conversão lenta mas direta.
- 7 das 10 derrotas nem chegaram a +300: **moagem posicional sem vantagem a proteger** (todas as muse/luna perdedoras).

### P3 — Configuração (correlações robustas, n pequeno)
| Fator | Efeito | Evidência |
|---|---|---|
| **rounds 6 + inline_child + preload** (vs r4) | ACPL 83.8/3.8B vs 132.7/5.6B | replicado em gemini (par tático: 114.7→42.5) e luna (88.7 vs 144.8) |
| **Sweet spot r6+noascii+tático+factual+hist12** | **3W–0L, ACPL médio 46.9, 1.0 blunder/jogo** | gemini-01v2, gemini-03v2, luna-05 (+2 snapshots fortes) |
| ascii no pacote L0 | 0W–3L, ACPL 155.8 | (caveat: confundido com cor/diretivo) |
| hist 12 > hist 6 | melhor em 2/2 pares R1 | hist 32 (luna-02): sem ganho, perdeu |
| muse medium vs low | ACPL 46.9/1B vs ~110/2.3B | replica H1 "medium é o sweet spot de esforço" (n=1 vs 3) |
| Diretivos | TACTICAL PRIORITIES: 3W–1L em 2 modelos; GUARDIAN: melhor ACPL (61.0) e menos blunders (1.5) | king-safety/spatial/trio/solid: 1W–7L |
| **Diretiva textual de "verificação" NÃO protege** | luna-03 "KING SAFETY WITH ENFORCED VERIFICATION": 0–1, 7 blunders | pedir ao modelo que confira não funciona; o guardian v2 (com rounds 6) foi melhor |

### P4 — Perfil do oponente SF-1320
- Contra pressão fraca ele é **sólido**: 4 derrotas dos modelos com **zero** blunders do 1320 (muse×2, luna-04, luna-02 — ACPL dele 22–47).
- Em jogos de erro mútuo (gemini R1/R2-02), ele **erra também (5,1 blunders/jogo em média) mas pune por último**; os modelos desperdiçam erros dele (luna-03: o 1320 erra r6528 no ply 52 e mesmo assim vence).
- **Implicação:** há pontos na mesa — o 1320 dá ~5 erros/jogo — mas aproveitá-los exige não morrer primeiro na própria tática.

## 4. Caminho recomendado de exploração (priorizado)

1. **Ataque à cegueira tática de 1 lance (barreira #1, 6/10 derrotas): nova tool L0 computada de ameaças.** Proposta: `board_inspect query=threats` (ou `board_threats`) que o **harness calcula** (xeques/capturas/mate-em-1 do adversário por candidato) e entra no pacote antes do `board_finalize`. Justificativa: diretiva textual pedindo verificação falhou (luna-03 0–1); computação determinística pelo kernel não depende do modelo "lembrar" de conferir. É exploração dentro do Zugzwang (runtime + chess plugin), sem mudar de modelo. → candidata a work order ZGW-0109.
2. **Benchmark A/B de diretivo no campeão atual:** gemini-3.8-flash-low, r6+inline+preload+noascii+hist12+factual, n=5 cada: `TACTICAL PRIORITIES v2` vs `TACTICAL GUARDIAN v2`. É o único fator de topo ainda não isolado (empate técnico entre os dois), e a infraestrutura já existe (`experiments/zgx/fullgames5/` + single-flight do agy).
3. **Modo conversão no harness:** quando o pacote indicar eval ≥ +300 a favor, injetar seção no system prompt ("você está ganhando: priorize segurança do rei e linhas forçadas; não expanda") — mira os 3 jogos desperdiçados com pico ≥ +300 e as derrotas por derrocada de rei no final.
4. **Muse medium continua viva:** ACPL 46.9 com 1 blunder é o melhor muse já medido; mas o jogo atual está em piora posicional lenta (−460 no ply 104). Hipótese nova: o diretivo tático cobre tática, não moagem posicional — um 4º fator a testar em muse é **diretiva posicional/profilática** (não tática) com medium.
5. **Não investir em:** ascii no pacote (0W–3L), histórico > 12 (32 não ajudou), rounds < 6, e nas vias GLM/Opus/Sonnet enquanto gemini/muse/luna resolverem o final.

## 5. Contexto de arena (ZGW-0108, vs humano)

5 partidas criadas na UI; gemini low venceu a única decidida até agora em 22 plies (`arena-20260909-010612`: 0–1, ACPL do modelo 8.0/0 blunders — o gemini low é claramente forte oponente para humano casual). As demais em andamento/curtas.

## 6. Limitações

- n pequeno em toda comparação (nenhum fator isolado com n>8); confounds rounds/inline/hist12/diretivos-v2 inseparáveis por design do R2.
- Regrets ≥1000 incluem ruído de mate-score (clamp reduz, não elimina); parte do histograma de final reflete jogos já decididos.
- luna-02/03: análise por lance do trecho final aproximada (PGN original truncado; reconstruído do watcher ao vivo).
- Muse R2-01 é snapshot (104+ plies, em andamento) — ACPL válido, W/L não.

## Apêndice — tabela mestre (vs SF1320)

Ver `games_dataset.json` (campos completos + trajetórias). Resumo:

| jogo | trilha | diretivo | outcome | plies | mACPL | mB | peak |
|---|---|---|---|---|---|---|---|
| full-01 | R1 | tactical-memory | **W** | 135 | 114.7 | 7 | mate |
| full-02 | R1 | spatial-ascii | L | 96 | 190.9 | 8 | +9995 (perdido) |
| full-03 | R1 | king-safety-hist | **W** | 61 | 110.9 | 4 | mate |
| full-04 | R1 | grandmaster-black | Lincomp | 195 | 171.9 | 16 | +97 |
| full-05 | R1 | tactical-trio | L | 40 | 143.5 | 3 | +666 (perdido) |
| muse-01 | R1 | tactical-memory | L | 64 | 117.7 | 4 | +151 |
| muse-02 | R1 | spatial-ascii | L | 44 | 104.5 | 2 | +78 |
| muse-03 | R1 | king-safety-hist | L | 46 | 107.8 | 1 | +30 |
| glm-01 | R1 | — | inc | 6 | 6.3 | 0 | — |
| opus-01/02, sonnet-01 | R1 | — | inc | 10/4/20 | ≤74 | ≤1 | — |
| gemini-01-v2 | R2 | tactical-memory | **W** | 83 | 42.5 | 1 | mate |
| gemini-02-v2 | R2 | king-safety | L | 164 | 156.5 | 12 | +407 (perdido) |
| gemini-03-v2 | R2 | tactical-guardian | **W** | 67 | 28.0 | 1 | mate |
| luna-01 | luna | guardian | inc | 54 | 78.8 | 2 | +549 |
| luna-02 | luna | deep-history(32) | L | 58 | 90.2 | 2 | +152 |
| luna-03 | luna | ks-enforced | L | 76 | 147.5 | 7 | +163 |
| luna-04 | luna | solid (r2) | L | 52 | 144.8 | 3 | +57 |
| luna-05 | luna | tactical-memory | **W** | 65 | 38.1 | 0 | mate |
| muse-r2-01 | muse-R2 | guardian-medium | em jogo | 104+ | 46.9 | 1 | +310 (ply 4) |
