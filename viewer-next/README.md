# viewer-next — Match Desk (Vite + React + TS + Tailwind v4)

Substituto moderno do `viewer/` (vanilla). Somente leitura, consome o snapshot
`data/data.json` gerado por `scripts/build_readonly_viewer.py`.

## Rodar

```bash
# 1. snapshot de dados (raiz do worktree)
uv run python scripts/build_readonly_viewer.py --workspace .
# 2. copiar o snapshot para o public do app (dev) ou dist (build)
mkdir -p viewer-next/public/data && cp viewer/data.json viewer-next/public/data/
# 3. dev server (HMR)
cd viewer-next && npm run dev            # http://localhost:5173
# ou build de produção
npm run build && npm run preview
```

`vite.config.ts` faz proxy de `/data` → `http://127.0.0.1:4173` (servidor
estático do `viewer/` legado), então `npm run dev` funciona com o snapshot de
lá. Em produção, sirva `dist/` com qualquer estático e mantenha `data/data.json`
ao lado do `index.html`.

## Camadas de observabilidade

- **L0 Operação** — todas as partidas: KPIs, tabela de runs, lances por
  experimento, tokens por run, latência p50/p95.
- **L1 Partida** — replay (chessground, engine do lichess), latência/tokens por
  decisão (uPlot, motor do Grafana), lista de lances com status de call.
- **L2 Profundo** — proveniência (protocol hash, assistência), task redigida,
  métricas post-hoc, eventos brutos, visão 3D (three.js).

Realtime = polling leve do snapshot (15s) + botão recarregar; o app nunca
escreve no workspace.

## Engine local no browser (só visualização)

A camada Partida tem barrinha de eval realtime (SF18 WASM, `stockfish` npm)
+ configurador (depth padrão 18, threads 2, hash 1024MB, força máxima/Elo/Skill).
É **somente leitura visual**: nunca entra no banco nem na análise oficial
(`scripts/analyze_deep.py` é o caminho oficial). Sem COOP/COEP usa o flavor
single-thread; com isolamento usa o multi-thread.
