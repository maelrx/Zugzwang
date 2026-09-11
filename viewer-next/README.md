# viewer-next — Match Desk (Vite + React + TS + Tailwind v4)

Biblioteca de pesquisa em modo leitura, com arena interativa local: biblioteca
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

A biblioteca atualiza o snapshot a cada 15 s. A arena salva suas partidas
através do serviço local e o histórico acompanha as análises a cada 3 s.

## Jogar e histórico (ZGW-0108–0110)

`#jogar` abre a arena humano × modelo. `#historico` lista todas as partidas,
inclusive em andamento, com busca e filtro. O replay permite selecionar
cada lance, reproduzir a sequência, virar o tabuleiro, copiar FEN e baixar
PGN. O viewer usa `/play/api`, via proxy local para 127.0.0.1:4191.

```bash
# Na raiz do checkout que contém a arena:
uv run python -m zugzwang_cli.arena.server --port 4191
```

Cada lance é salvo em `out/arena/` (JSON + PGN); chamadas de modelos ficam
em JSONL privado. Ao encerrar por regra ou desistência, o serviço inicia
Stockfish nativo com `go depth 20` para a posição inicial e cada meio-lance.
Usa o binário instalado no PATH (override: `ZGW_STOCKFISH_PATH`), força máxima,
2 threads e 128 MB de hash. Um worker local mantém as análises em fila;
continuam mesmo com a página fechada. O processo do serviço deve permanecer
ligado. Não há download de engine nem novas dependências.

Checkpoint, perfil do engine, resultados e tentativas ficam em
`out/arena/analysis/`. A retomada após reiniciar não repete posições salvas.
Falhas ficam visíveis e podem ser retomadas pelo histórico; não há retry
oculto. A avaliação só é liberada depois que a partida termina, sempre pela
perspectiva das brancas. Profundidade efetiva e mates são mostrados
explicitamente. Isso é revisão local da arena, não análise científica do
kernel nem rating. A biblioteca de pesquisa continua somente leitura.

Os temas Escuro e Profundo usam superfícies quase pretas com acentos dourados
e texto claro, incluindo no histórico e na biblioteca. O modo Claro e as
preferências de aparência continuam disponíveis.


### Interface Jogar e Histórico (ZGW-0111)

Jogar usa tabuleiro central e configuração recolhida durante a partida. Histórico
oferece busca, filtros e replay com avaliação e notação sincronizadas. O layout
adapta-se ao celular; a promoção suporta teclado e Escape. Veja
[ZGW-0111](../docs/work-orders/ZGW-0111.md) para escopo e evidências.
