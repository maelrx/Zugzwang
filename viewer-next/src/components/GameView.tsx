import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Run } from "@/lib/types";
import { modelLabel, resultLabel, routeFor } from "@/lib/presentation";
import type { parseRoute } from "@/lib/presentation";
import { fmtNum, fmtMs } from "@/lib/format";
import { Board } from "./Board";
import { AnalysisPanel } from "./AnalysisPanel";
import { UPlotChart } from "./UPlotChart";
import type { SeriesDef } from "./UPlotChart";
import { Icon } from "./Icon";
import { CopyButton } from "./CopyButton";
const Board3D = lazy(() => import("./Board3D").then(m => ({ default: m.Board3D })));
const LiveEval = lazy(() => import("./LiveEval").then(m => ({ default: m.LiveEval })));
const LATENCY: SeriesDef[] = [{ label: "Tempo de resposta", color: "var:--color-chart-a", fill: true }];
const TOKENS: SeriesDef[] = [{ label: "Tokens de saída", color: "var:--color-chart-b", fill: true }];

export function GameView({ run, view, route }: { run: Run; view: "game" | "analysis"; route: ReturnType<typeof parseRoute> }) {
  const epIndex = Math.min(route.episode, Math.max(0, run.episodes.length - 1));
  const ep = run.episodes[epIndex];
  const max = ep?.moves?.length ?? 0;
  const ply = Math.min(route.ply ?? max, max);
  const [playing, setPlaying] = useState(false);
  const [orientation, setOrientation] = useState<"white" | "black">("white");
  const [view3d, setView3d] = useState(false);
  const [engine, setEngine] = useState(false);
  const list = useRef<HTMLDivElement>(null);
  const seek = useCallback((next: number | undefined, pause = true, episode = epIndex) => {
    if (pause) setPlaying(false);
    window.history.replaceState(null, "", routeFor(run.id, view, episode, next));
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  }, [run.id, view, epIndex]);
  useEffect(() => {
    if (!playing || view !== "game") return;
    const timer = window.setTimeout(() => { if (ply >= max) setPlaying(false); else seek(ply + 1, false); }, 800);
    return () => window.clearTimeout(timer);
  }, [playing, ply, max, seek, view]);
  useEffect(() => {
    if (view !== "game") return;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (event.altKey || event.ctrlKey || event.metaKey || target.closest("input,select,textarea,[contenteditable=true]")) return;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); seek(Math.max(0, Math.min(max, ply + (event.key === "ArrowLeft" ? -1 : 1)))); }
    };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [ply, max, seek, view]);
  useEffect(() => { const selected = list.current?.querySelector<HTMLElement>('[aria-current="step"]'); if (selected && list.current) list.current.scrollTop = selected.offsetTop - list.current.offsetTop - list.current.clientHeight / 2; }, [ply, view]);
  const latency = useMemo(() => { const moves = (ep?.moves ?? []).filter(m => m.actorKind === "Model" && typeof m.provider?.latencyMs === "number"); return { x: moves.map(m => m.ply), y: [moves.map(m => m.provider!.latencyMs / 1000)] }; }, [ep]);
  const tokens = useMemo(() => { const moves = (ep?.moves ?? []).filter(m => m.actorKind === "Model" && typeof m.provider?.tokensOut === "number"); return { x: moves.map(m => m.ply), y: [moves.map(m => m.provider!.tokensOut!)] }; }, [ep]);
  if (!ep) return <div className="empty-state"><Icon name="grid" size={32}/><h2>Ainda não há episódio disponível</h2><p>Os lances aparecerão quando forem incluídos na próxima leitura.</p></div>;
  const current = ply > 0 ? ep.moves[ply - 1] : undefined;
  const fen = ply === 0 ? ep.positions?.[0]?.fen ?? null : current?.fenAfter ?? null;
  const rows = new Map<number, { White?: number; Black?: number }>();
  ep.moves.forEach((m, i) => { const number = m.moveNumber || Math.floor((m.ply - 1) / 2) + 1; const pair = rows.get(number) ?? {}; pair[m.side] = i; rows.set(number, pair); });
  const opponent = ep.moves.find(m => m.actorKind !== "Model")?.actorKind ?? "Oponente não informado";
  const modelSide = ep.moves.find(m => m.actorKind === "Model")?.side;
  const player = (side: "White" | "Black") => side === modelSide ? modelLabel(run) : opponent;
  const metricIds = new Set((run.metrics ?? []).filter(m => m.episodeId === ep.id).map(m => m.stepId));
  return <>
    <div className="episode-bar"><span className="result-summary">{resultLabel(ep)}</span>{run.episodes.length > 1 && <label>Episódio <select aria-label="Selecionar episódio" value={epIndex} onChange={e => seek(undefined, true, Number(e.target.value))}>{run.episodes.map((e, i) => <option key={e.id} value={i}>{i + 1} · {resultLabel(e)}</option>)}</select></label>}<span className="quiet-label">{max} meios-lances registrados</span></div>
    {view === "analysis" ? <div className="analysis-view"><div className="notice"><Icon name="chart"/><div><strong>Análise registrada</strong><p>Estas métricas vêm do avaliador pós-jogo. A avaliação visual do navegador é independente e não altera estes resultados.</p></div></div><AnalysisPanel episode={ep} metrics={run.metrics ?? []} onSelectPly={p => { window.location.hash = routeFor(run.id, "game", epIndex, p); }}/><div className="chart-grid"><section className="surface"><div className="section-heading"><h2>Tempo por decisão</h2><span>segundos</span></div>{latency.x.length > 1 ? <UPlotChart x={latency.x} ys={latency.y} series={LATENCY} height={200} yLabel="s"/> : <p className="empty-inline">Ainda não há decisões suficientes para esta curva.</p>}</section><section className="surface"><div className="section-heading"><h2>Saída por decisão</h2><span>tokens reportados</span></div>{tokens.x.length > 1 ? <UPlotChart x={tokens.x} ys={tokens.y} series={TOKENS} height={200}/> : <p className="empty-inline">Ainda não há tokens suficientes para esta curva.</p>}</section></div></div> : <>
      <div className="game-layout"><section className="board-section" aria-label="Replay da partida">
        <div className="player-strip"><span className={`piece-dot ${orientation === "white" ? "black" : "white"}`}/><div><span>{orientation === "white" ? "Pretas" : "Brancas"}</span><strong>{player(orientation === "white" ? "Black" : "White")}</strong></div><span className="quiet-label">{orientation === "white" ? "↓" : "↑"}</span></div>
        <div className="board-stage">{engine && <Suspense fallback={<span className="quiet-label">…</span>}><LiveEval fen={fen} gameKey={`${run.id}:${epIndex}`}/></Suspense>}<div className="board-wrap">{fen ? view3d ? <Suspense fallback={<div className="board-loading">Preparando tabuleiro 3D…</div>}><Board3D fen={fen}/></Suspense> : <Board fen={fen} lastUci={current?.uci ?? null} orientation={orientation}/> : <div className="board-loading">Posição não disponível neste lance.</div>}</div></div>
        <div className="player-strip bottom"><span className={`piece-dot ${orientation === "white" ? "white" : "black"}`}/><div><span>{orientation === "white" ? "Brancas" : "Pretas"}</span><strong>{player(orientation === "white" ? "White" : "Black")}</strong></div><span className="quiet-label">{ply === max ? "Última posição" : `Posição ${ply}`}</span></div>
        <div className="replay-bar"><button className="icon-button" disabled={!ply} onClick={() => seek(0)} aria-label="Posição inicial"><Icon name="first"/></button><button className="icon-button" disabled={!ply} onClick={() => seek(ply - 1)} aria-label="Lance anterior"><Icon name="back"/></button><button className="button primary play-button" disabled={!max} onClick={() => { if (ply >= max) seek(0, false); setPlaying(p => !p); }}><Icon name={playing ? "pause" : "play"} size={15}/>{playing ? "Pausar" : "Reproduzir"}</button><button className="icon-button" disabled={ply >= max} onClick={() => seek(ply + 1)} aria-label="Próximo lance"><Icon name="arrow"/></button><button className="icon-button" disabled={ply >= max} onClick={() => seek(max)} aria-label="Última posição"><Icon name="last"/></button></div>
        <div className="timeline"><span>{ply}</span><input type="range" min={0} max={max} value={ply} onChange={e => seek(Number(e.target.value))} aria-label="Posição no replay"/><span>{max}</span></div>
        <div className="board-tools"><button className="button compact" disabled={view3d} onClick={() => setOrientation(o => o === "white" ? "black" : "white")}><Icon name="flip" size={15}/>Girar</button><button className="button compact" aria-pressed={view3d} onClick={() => setView3d(v => !v)}>Tabuleiro 3D</button><CopyButton text={fen ?? ""} label="Copiar FEN"/><button className="button compact" aria-pressed={engine} onClick={() => setEngine(e => !e)}>Avaliação visual</button></div>
        {engine && <p className="helper-text">Stockfish no navegador, somente visual. Não é a análise registrada.</p>}
      </section><div className="game-right"><section className="moves-section surface"><div className="section-heading"><div><h2>Lances da partida</h2><p>Selecione um lance para examinar a posição.</p></div>{run.status === "RUNNING" && <button className="button compact" aria-pressed={route.ply === undefined} onClick={() => seek(undefined)}>Acompanhar</button>}</div><div className="moves-header"><span>#</span><span>Brancas</span><span>Pretas</span></div><div className="move-list" ref={list}>
        {[...rows].map(([number, pair]) => <div className="move-pair" key={number}><span className="move-number">{number}.</span>{(["White", "Black"] as const).map(side => { const idx = pair[side]; const m = idx === undefined ? undefined : ep.moves[idx]; return m && idx !== undefined ? <button key={side} onClick={() => seek(idx + 1)} aria-current={ply === idx + 1 ? "step" : undefined} aria-label={`Lance ${number}${side === "Black" ? " pretas" : " brancas"}: ${m.san ?? m.display}`}><strong>{m.san ?? m.display}</strong>{m.provider && <span title={`${m.provider.attempts} tentativa(s)`}>{fmtMs(m.provider.latencyMs)}</span>}{metricIds.has(m.stepId) && <i title="Possui análise registrada"/>}</button> : <span key={side} className="missing-move">—</span>; })}</div>)}
        {!max && <p className="empty-inline">Aguardando o primeiro lance registrado.</p>}</div><div className="moves-footer"><span>← → para navegar</span><span>{ply === 0 ? "Posição inicial" : `${current?.moveNumber ?? ply}${current?.side === "Black" ? "…" : "."} ${current?.san ?? current?.display ?? ""}`}</span></div></section>
        <section className="decision-summary"><div className="section-heading"><h2>{current ? "Decisão selecionada" : "Antes do primeiro lance"}</h2><span>{current?.actorKind === "Model" ? "Modelo" : current?.actorKind ?? ""}</span></div><dl className="facts-grid"><div><dt>Lance</dt><dd>{current?.san ?? current?.display ?? "—"}</dd></div><div><dt>Tempo de resposta</dt><dd>{current?.provider ? fmtMs(current.provider.latencyMs) : "—"}</dd></div><div><dt>Tentativas</dt><dd>{current?.provider?.attempts ?? "—"}</dd></div><div><dt>Tokens de saída</dt><dd>{current?.provider?.tokensOut == null ? "—" : fmtNum(current.provider.tokensOut)}</dd></div></dl><a className="text-link" href={routeFor(run.id, "analysis", epIndex, ply)}>Consultar análise registrada <Icon name="arrow" size={15}/></a></section>
      </div></div>
      <details className="technical-details"><summary>Posição e identificadores</summary><dl className="facts-grid"><div><dt>Episódio</dt><dd className="mono">{ep.id}</dd></div><div><dt>Step selecionado</dt><dd className="mono">{current?.stepId ?? "Posição inicial"}</dd></div></dl><code className="fen-text">{fen ?? "FEN não disponível"}</code></details>
    </>}
  </>;
}
