# viewer-next — Match Desk (Vite + React + TS + Tailwind v4)

Observabilidade local e somente leitura das execuções do kernel: biblioteca
de pesquisas, replay de partidas (chessground), análise post-hoc (uPlot,
motor do Grafana), evidências/proveniência e comparação entre execuções.

Consome o snapshot `public/data/data.json`, publicado por
`scripts/regen-snapshot.sh` a partir de `scripts/build_readonly_viewer.py`.

## Rodar

```bash
# 1. snapshot de dados ao vivo (raiz do worktree; loop de 30 s, 0 = uma passada)
viewer-next/scripts/regen-snapshot.sh &
# 2. dev server
cd viewer-next && npx vite --host 127.0.0.1 --port 4190 --strictPort
```

`npm run dev` também funciona (porta 5173). Build de produção:
`npm run build && npm run preview`.

Primeiro uso do worktree: `npm ci` + `node scripts/setup-engine.cjs`
(prepara o Stockfish WASM em `public/engine/`).

## Experiência

- **Biblioteca** — execuções com estado/resultado, lances, chamadas e
  atividade; busca, filtros por modelo/experimento, comparação (até 3).
- **Partida** — replay com tabuleiro (chessground), lances com status de
  call, latência/tokens por decisão (uPlot), barra de avaliação local
  opcional (SF18 WASM, somente visual — nunca entra na análise oficial;
  `scripts/analyze_deep.py` é o caminho registrado).
- **Análise** — qualidade das decisões do avaliador post-hoc.
- **Evidências** — proveniência, hashes, eventos brutos.
- **Aparência** (topbar) — temas Escuro/Profundo/Claro, texturas de papel
  (papel/fibra/linho/grão, SVG feTurbulence em data-URI, sem dependências) e
  escala de fonte 90–130%; persistido no navegador (`localStorage`).

Realtime = polling leve do snapshot (15 s) + botão recarregar; o app nunca
escreve no workspace.
