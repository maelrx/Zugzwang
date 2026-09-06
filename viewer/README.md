# Viewer local

Viewer estático e somente leitura dos runs persistidos no workspace (ZGW-0077).

## Gerar / atualizar o recorte

```bash
uv run python scripts/build_readonly_viewer.py
uv run python scripts/build_readonly_viewer.py --completed-only
uv run python scripts/build_readonly_viewer.py --limit 100
```

O builder é a única ponte entre o workspace e o navegador: lê SQLite + CAS,
projeta runs/episódios/lances/métricas/eventos em `viewer/data.js`, escreve o
manifesto de polling em `viewer/meta.json` e o sprite de peças em
`viewer/pieces.js`. Não copia requests/responses brutos e redige chaves
sensíveis (`_redact`); `value_json` é projetado com teto de tamanho.

## Servir localmente

```bash
python3 -m http.server 4173 --bind 127.0.0.1 --directory viewer
```

Abra <http://127.0.0.1:4173/>. O navegador lê apenas `data.js`, `meta.json` e
`pieces.js` — nunca SQLite ou CAS.

## Auto-refresh (sem perder o replay)

O viewer faz poll de `meta.json` a cada 15 s (fetch same-origin, sem reload).
Quando o sha muda, aparece a pílula **"nova snapshot — atualizar sem perder o
replay"**: o estado atual (run, episódio, ply, busca, filtros, pins) é
preservado e só aplicado na hora que o operador clicar. Se `meta.json` não
existir (snapshot antiga), o viewer avisa no rodapé e segue funcionando.

## O que tem na tela

- **Replay**: tabuleiro com coordenadas + gauge de eval (brancas, display
  apenas), transporte com velocidades (0.5×–4×), atalhos (`←`/`→` navegam,
  `espaço` reproduz, `Home`/`End`), lista de lances com ponto de classe +
  CPL + rank, eventos com busca (40 visíveis), fatos do run (H/K, tarefa).
- **Análise da partida**: KPIs derivados só do já publicado pelo evaluator
  pós-hoc — ACPL (`mean(chess.cpl)`), ΔWDL médio (`mean(chess.wdl_loss)`),
  top-1 (acordo com bestmove) / top-3 (`chess.chosen_rank ≤ 3`), classes
  v1.0.0 (blunder ≥300cp · erro ≥100cp · imprecisão ≥50cp) — mais curva de
  eval (`chess.cp_before`, clamp ±1200), barras de CPL, CPL por fase
  (`dimensions.phase`), rank + transições de mate, PV por lance, piores
  lances clicáveis e prova do engine (config registrada + evaluator@versão
  + sha do binário). Cada seção exibe sua fórmula; "n/a" = evaluator não
  publicou observação naquele registro.
- **Comparar**: fixe até 4 runs com 📌 na lista; tabela lado a lado com
  melhor-da-coluna em verde. Comparar não estabelece claim de sistema.
- **Filtros**: todos / verdes / falhas / **com CPL**, mais busca textual.
  Estado sincronizado na URL (`?run=&view=&episode=&ply=&q=&status=&cmp=`).

## Invariantes

- 100% estático: sem backend, sem React/Vite, sem engine no navegador —
  Stockfish segue post-hoc (ADR-024, GATE-006: sem redistribuir binário).
- Sem escrita além de `data.js` + `meta.json` regenerados pelo builder.
- Sem claims de Elo a partir de run único; sem export público (GATE-005).
