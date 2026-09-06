import { useEffect, useMemo, useRef, useState } from "react";
import type { Run, Episode } from "@/lib/types";
import { runStats, modelDecisions, modelName } from "@/lib/types";
import { fmtNum, fmtMs, fmtDur } from "@/lib/format";
import { Board } from "./Board";
import { Board3D } from "./Board3D";
import { LiveEval } from "./LiveEval";
import { AnalysisPanel } from "./AnalysisPanel";
import { UPlotChart } from "./UPlotChart";
import type { SeriesDef } from "./UPlotChart";

const SERIES_LAT: SeriesDef[] = [{ label: "segundos", color: "#8eaae9", fill: true }];
const SERIES_CUM: SeriesDef[] = [
  { label: "in", color: "#8eaae9", fill: true },
  { label: "out", color: "#e8a865", fill: true },
];
const SERIES_OUT: SeriesDef[] = [{ label: "out", color: "#6fd3ab" }];
const SERIES_EVAL: SeriesDef[] = [{ label: "eval brancas (cp)", color: "#e8a865", fill: true }];

interface Props {
  run: Run;
  onBack: () => void;
  onDeep: () => void;
}

export function GameView({ run, onBack, onDeep }: Props) {
  const [epIdx, setEpIdx] = useState(0);
  const [ply, setPly] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [view3d, setView3d] = useState(false);

  const ep: Episode | undefined = run.episodes?.[epIdx];
  const max = ep?.moves?.length ?? 0;

  const plyRef = useRef(ply);
  // Latest-value ref so the play interval reads fresh ply without
  // side-effects inside the setState updater (StrictMode-safe).
  // eslint-disable-next-line react/refs
  plyRef.current = ply;

  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(() => {
      if (plyRef.current >= max) {
        setPlaying(false);
        return;
      }
      setPly(plyRef.current + 1);
    }, 850);
    return () => window.clearInterval(t);
  }, [playing, max]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || (e.target as HTMLElement).isContentEditable) return;
      if (e.target instanceof HTMLButtonElement && (e.key === " " || e.key === "Enter")) return;
      if (e.key === "ArrowLeft") setPly((p) => Math.max(0, p - 1));
      if (e.key === "ArrowRight") setPly((p) => Math.min(max, p + 1));
      if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [max]);

  const decisions = useMemo(() => (ep ? modelDecisions(ep) : []), [ep]);
  const s = useMemo(() => runStats(run), [run]);

  const move = ply > 0 ? ep?.moves?.[ply - 1] : undefined;
  const fen = ply === 0 ? (ep?.positions?.[0]?.fen ?? null) : (move?.fenAfter ?? null);
  const cur = ep?.moves?.[ply - 1];

  const chartData = useMemo(() => {
    const latX = decisions.map((d) => d.ply);
    return {
      latX,
      ysLat: [decisions.map((d) => d.latencyMs / 1000)] as [number[]],
      ysCum: [decisions.map((d) => d.cumIn), decisions.map((d) => d.cumOut)] as [number[], number[]],
      ysPer: [decisions.map((d) => d.tokensOut)] as [number[]],
    };
  }, [decisions]);
  const { latX, ysLat, ysCum, ysPer } = chartData;

  const evalCurve = useMemo(() => {
    if (!ep) return null;
    const byStep = new Map<string, number>();
    for (const m of run.metrics ?? []) {
      if (m.metric !== "chess.engine_score_before" || m.episodeId !== ep.id) continue;
      if (typeof m.valueNum === "number" && m.stepId) byStep.set(m.stepId, m.valueNum);
    }
    const xs: number[] = [];
    const ys: number[] = [];
    for (const mv of ep.moves ?? []) {
      const v = byStep.get(mv.stepId);
      // cp only: mate positions carry no cp score (mate_transition covers
      // them), so the curve simply has no point there. Clamp display range.
      if (typeof v === "number") {
        xs.push(mv.ply);
        ys.push(Math.max(-2000, Math.min(2000, v)));
      }
    }
    return xs.length > 1 ? { x: xs, ys: [ys] as [number[]] } : null;
  }, [run.metrics, ep]);

  const sanLines = useMemo(() => {
    const out: string[] = [];
    const moves = ep?.moves ?? [];
    for (let i = 0; i < moves.length; i += 2) {
      out.push(`${i / 2 + 1}. ${moves[i]?.san ?? "?"} ${moves[i + 1]?.san ?? ""}`);
    }
    return out;
  }, [ep]);

  if (!ep) return <div className="py-16 text-center text-muted">episódio não encontrado</div>;

  return (
    <div className="space-y-3.5">
      <div className="flex flex-wrap items-center gap-2.5">
        <h2 className="text-lg font-semibold">{run.experiment}</h2>
        <span className="font-mono text-[11px] text-muted">{run.id}</span>
        <span className="font-mono text-[11px] text-faint">· {modelName(run)}</span>
        {run.status === "RUNNING" && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-warn/15 px-2 py-0.5 font-mono text-[10px] text-warn">
            <span className="size-1.5 animate-pulse rounded-full bg-warn" /> live
          </span>
        )}
        <div className="flex-1" />
        <button onClick={onBack} className="rounded-md border border-line bg-panel px-3 py-1.5 text-[12.5px] hover:border-faint">
          ← operação
        </button>
        <button onClick={onDeep} className="rounded-md bg-paper px-3 py-1.5 text-[12.5px] font-semibold text-ink hover:opacity-90">
          profundo →
        </button>
      </div>

      <div className="grid items-start gap-3.5 xl:grid-cols-[minmax(340px,440px)_1fr]">
        <section className="rounded-lg border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-faint">posição</p>
              <h3 className="text-sm font-semibold">Tabuleiro</h3>
            </div>
            <div className="flex items-center gap-2">
              {run.episodes.length > 1 && (
                <select
                  value={epIdx}
                  onChange={(e) => { setEpIdx(+e.target.value); setPly(0); setPlaying(false); }}
                  className="rounded border border-line bg-panel2 px-2 py-1 font-mono text-[11px]"
                  aria-label="Episódio"
                >
                  {run.episodes.map((e, i) => (
                    <option key={e.id} value={i}>ep {i + 1} · {e.result}</option>
                  ))}
                </select>
              )}
              <button
                onClick={() => setView3d((v) => !v)}
                className={"rounded border px-2 py-1 font-mono text-[11px] " + (view3d ? "border-accent text-accent" : "border-line text-muted hover:text-paper")}
                title="alternar visão 3D"
              >
                3D
              </button>
            </div>
          </div>
          <div className="p-3">
            <div className="flex gap-2">
              <LiveEval fen={fen} gameKey={`${run.id}:${epIdx}`} />
              <div className="min-w-0 flex-1">
                {view3d ? <Board3D fen={fen} /> : <Board fen={fen} lastUci={cur?.uci ?? null} />}
              </div>
            </div>
            <div className="mt-2.5 flex items-center gap-2">
              <button onClick={() => setPly(0)} className="rounded border border-line px-2 py-1 font-mono text-[11.5px] hover:border-faint" title="início" aria-label="Ir para o primeiro lance">|◀</button>
              <button onClick={() => setPly((p) => Math.max(0, p - 1))} className="rounded border border-line px-2 py-1 font-mono text-[11.5px] hover:border-faint" title="anterior" aria-label="Voltar um lance">◀</button>
              <button
                onClick={() => setPlaying((p) => !p)}
                className="rounded bg-paper px-3 py-1 text-[12px] font-semibold text-ink hover:opacity-90"
              >
                {playing ? "pausar" : "reproduzir"}
              </button>
              <button onClick={() => setPly((p) => Math.min(max, p + 1))} className="rounded border border-line px-2 py-1 font-mono text-[11.5px] hover:border-faint" title="próximo" aria-label="Avançar um lance">▶</button>
              <button onClick={() => setPly(max)} className="rounded border border-line px-2 py-1 font-mono text-[11.5px] hover:border-faint" title="fim" aria-label="Ir para o último lance">▶|</button>
              <input
                type="range"
                min={0}
                max={max}
                value={ply}
                onChange={(e) => setPly(+e.target.value)}
                className="flex-1 accent-accent"
                aria-label="ply"
              />
              <span className="min-w-14 text-right font-mono text-[11px] text-muted">{ply}/{max}</span>
            </div>
            <div className="mt-1.5 h-5 font-mono text-[11px] text-muted">
              {cur ? (
                <>
                  <span className={cur.side === "White" ? "text-paper" : "text-faint"}>{cur.side === "White" ? "brancas" : "pretas"}</span>
                  {" · "}{cur.san ?? cur.display}
                  {" · "}{cur.actorKind === "Model" ? "modelo" : cur.actorKind === "Stockfish" ? "stockfish" : cur.actorKind}
                  {cur.provider ? ` · ${fmtMs(cur.provider.latencyMs)}` : ""}
                </>
              ) : (
                "posição inicial"
              )}
            </div>
          </div>
        </section>

        <div className="grid gap-3.5">
          <section className="rounded-lg border border-line bg-panel">
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest text-faint">ritmo do modelo</p>
                <h3 className="text-sm font-semibold">Latência por decisão</h3>
              </div>
              <small className="font-mono text-[10.5px] text-faint">
                {decisions.length} decisões · pico {decisions.length ? fmtMs(Math.max(...decisions.map((d) => d.latencyMs))) : "—"}
              </small>
            </div>
            <div className="px-2 py-1">
              {latX.length > 1 ? (
                <UPlotChart x={latX} ys={ysLat} series={SERIES_LAT} yLabel="s" height={150} />
              ) : (
                <div className="py-10 text-center text-muted">sem telemetria de latência</div>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-line bg-panel">
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-widest text-faint">pós-jogo · stockfish</p>
                <h3 className="text-sm font-semibold">Avaliação por lance</h3>
              </div>
              <small className="font-mono text-[10.5px] text-faint">depth 20 · cp, teto ±20</small>
            </div>
            <div className="px-2 py-1">
              {evalCurve ? (
                <UPlotChart x={evalCurve.x} ys={evalCurve.ys} series={SERIES_EVAL} yLabel="cp" height={150} />
              ) : (
                <div className="py-10 text-center text-muted">sem análise profunda ainda — roda scripts/analyze_deep.py</div>
              )}
            </div>
            <div className="flex flex-wrap gap-3 px-4 pb-3 text-[11px] text-muted">
              <span className="inline-flex items-center gap-1.5"><span className="inline-block size-2.5 rounded-sm bg-accent"></span>eval das brancas antes de cada lance do modelo</span>
            </div>
          </section>

          <div className="grid gap-3.5 lg:grid-cols-2">
            <section className="rounded-lg border border-line bg-panel">
              <div className="border-b border-line px-4 py-2.5">
                <p className="font-mono text-[10px] uppercase tracking-widest text-faint">consumo acumulado</p>
                <h3 className="text-sm font-semibold">Tokens por decisão</h3>
              </div>
              <div className="px-2 py-1">
                {latX.length > 1 ? (
                  <UPlotChart
                    x={latX}
                    ys={ysCum}
                    series={SERIES_CUM}
                    height={150}
                  />
                ) : (
                  <div className="py-10 text-center text-muted">sem dados</div>
                )}
              </div>
            </section>
            <section className="rounded-lg border border-line bg-panel">
              <div className="border-b border-line px-4 py-2.5">
                <p className="font-mono text-[10px] uppercase tracking-widest text-faint">por lance do modelo</p>
                <h3 className="text-sm font-semibold">Tokens out / call</h3>
              </div>
              <div className="px-2 py-1">
                {latX.length > 1 ? (
                  <UPlotChart x={latX} ys={ysPer} series={SERIES_OUT} height={150} />
                ) : (
                  <div className="py-10 text-center text-muted">sem dados</div>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>

      <AnalysisPanel episode={ep} metrics={run.metrics ?? []} />

      <div className="grid gap-3.5 lg:grid-cols-2">
        <section className="rounded-lg border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-faint">partida</p>
              <h3 className="text-sm font-semibold">Lances</h3>
            </div>
            <small className="font-mono text-[10.5px] text-faint">← → navegam · espaço reproduz</small>
          </div>
          <div className="max-h-72 overflow-y-auto font-mono text-[12px]">
            {ep.moves.map((m, i) => {
              const p = m.provider;
              const dot = !p ? "" : p.status === "ok" ? "bg-ok" : p.status === "repaired" ? "bg-warn" : "bg-err";
              return (
                <button
                  key={m.stepId}
                  onClick={() => { setEpIdx(epIdx); setPly(i + 1); }}
                  className={`grid w-full grid-cols-[40px_1fr_auto_auto] items-baseline gap-2 px-3 py-[3px] text-left hover:bg-panel2 ${ply === i + 1 ? "bg-accent/10" : ""}`}
                >
                  <span className="text-faint">{Math.floor(i / 2) + 1}{m.side === "White" ? "." : "…"}</span>
                  <span>
                    <span className={`mr-1.5 inline-block size-[7px] rounded-full align-middle ${dot || "bg-transparent"}`} title={p ? p.status : m.actorKind} />
                    {m.san ?? m.display}
                  </span>
                  <span className="text-[10.5px] text-faint">{m.actorKind === "Model" ? "modelo" : m.actorKind === "Stockfish" ? "SF" : ""}</span>
                  <span className={`text-[10.5px] ${p && p.latencyMs > 60000 ? "text-warn" : "text-faint"}`}>{p ? fmtMs(p.latencyMs) : ""}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-4 py-2.5">
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">episódio</p>
            <h3 className="text-sm font-semibold">Sinais</h3>
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2.5 p-4 md:grid-cols-3">
            <Fact label="resultado" value={`${ep.result}${ep.winner ? " · " + ep.winner : ""}`} />
            <Fact label="duração" value={fmtDur(run.startedAt, run.finishedAt)} />
            <Fact label="lances" value={`${ep.stepsCommitted} (${s.plies} no run)`} />
            <Fact label="calls" value={`${s.calls} (attempts ${s.attempts})`} />
            <Fact label="reparos/timeouts" value={`${s.repaired} / ${s.timeouts}`} />
            <Fact label="tokens i/o" value={`${fmtNum(s.tokensIn)} / ${fmtNum(s.tokensOut)}`} />
            <Fact label="assistência" value={`${run.declaredAssistance ?? "—"} → ${run.effectiveAssistance ?? "—"}`} />
            <Fact label="protocolo" value={(run.protocolHash ?? "").slice(0, 14) + "…"} mono />
            <Fact label="custo" value={run.provider.costStatus} />
          </div>
          <div className="border-t border-line px-4 py-3">
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">pgn curto</p>
            <div className="mt-1.5 font-mono text-[11.5px] leading-7 text-muted">{sanLines.join("  ")}</div>
          </div>
        </section>
      </div>
    </div>
  );
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-faint">{label}</div>
      <div className={`mt-0.5 truncate text-[12.5px] ${mono ? "font-mono text-[11.5px]" : ""}`} title={value}>{value}</div>
    </div>
  );
}
