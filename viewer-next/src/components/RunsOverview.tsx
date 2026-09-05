import { useMemo } from "react";
import type { Run } from "@/lib/types";
import { runStats, modelName } from "@/lib/types";
import { fmtNum, fmtDur } from "@/lib/format";
import { UPlotChart } from "./UPlotChart";
import type { SeriesDef } from "./UPlotChart";

const SERIES_PLIES: SeriesDef[] = [{ label: "plies", color: "#8eaae9", fill: true }];
const SERIES_TOKENS: SeriesDef[] = [{ label: "tokens", color: "#e8a865", fill: true }];

function StatusPill({ run }: { run: Run }) {
  if (run.status === "RUNNING")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-warn/15 px-2 py-0.5 font-mono text-[10px] text-warn">
        <span className="size-1.5 animate-pulse rounded-full bg-warn" /> live
      </span>
    );
  if (run.status === "COMPLETED")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-ok/15 px-2 py-0.5 font-mono text-[10px] text-ok">
        <span className="size-1.5 rounded-full bg-ok" /> ok
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-err/15 px-2 py-0.5 font-mono text-[10px] text-err">
      <span className="size-1.5 rounded-full bg-err" /> {run.status.toLowerCase()}
    </span>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3">
      <div className="font-mono text-[10px] uppercase tracking-wider text-faint">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="text-[11.5px] text-muted">{sub}</div>}
    </div>
  );
}

export function RunsOverview({ runs, onOpen }: { runs: Run[]; onOpen: (id: string) => void }) {
  const totals = useMemo(() => {
    const acc = { plies: 0, calls: 0, in: 0, out: 0, live: 0, done: 0 };
    for (const r of runs) {
      const s = runStats(r);
      acc.plies += s.plies;
      acc.calls += s.calls;
      acc.in += s.tokensIn;
      acc.out += s.tokensOut;
      if (r.status === "RUNNING") acc.live++;
      if (r.status === "COMPLETED") acc.done++;
    }
    return acc;
  }, [runs]);

  const lastEp = (r: Run) => r.episodes?.[r.episodes.length - 1];

  // bars: plies per experiment (top 8)
  const byExp = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of runs) {
      const k = (r.experiment || "?").slice(0, 24);
      m.set(k, (m.get(k) ?? 0) + runStats(r).plies);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [runs]);

  const exp = useMemo(() => ({
    x: byExp.map((_, i) => i),
    ys: [byExp.map(([, v]) => v)] as [number[]],
  }), [byExp]);

  // bars: tokens per run (top 8)
  const byTok = useMemo(
    () =>
      runs
        .map((r) => ({ id: r.id, s: runStats(r) }))
        .map(({ id, s }) => ({ id, v: s.tokensIn + s.tokensOut }))
        .sort((a, b) => b.v - a.v)
        .slice(0, 8),
    [runs],
  );
  const tok = useMemo(() => ({
    x: byTok.map((_, i) => i),
    ys: [byTok.map((d) => d.v)] as [number[]],
  }), [byTok]);

  // stacked latency bands per run: p50/p95 max
  const latBands = useMemo(
    () =>
      runs
        .map((r) => {
          const lat = runStats(r).latencies.slice().sort((a, b) => a - b);
          return {
            id: r.id.slice(4, 14),
            p50: lat.length ? lat[Math.floor(lat.length * 0.5)] / 1000 : 0,
            p95: lat.length ? lat[Math.floor(lat.length * 0.95)] / 1000 : 0,
          };
        })
        .sort((a, b) => b.p95 - a.p95)
        .slice(0, 8),
    [runs],
  );

  return (
    <div className="space-y-3.5">
      <div className="grid grid-cols-2 gap-3.5 md:grid-cols-4">
        <Kpi label="partidas" value={String(runs.length)} sub={`${totals.live} live · ${totals.done} completas`} />
        <Kpi label="lances totais" value={fmtNum(totals.plies)} sub="todos os episódios" />
        <Kpi label="calls ao modelo" value={fmtNum(totals.calls)} sub="1 por decisão" />
        <Kpi label="tokens in/out" value={`${fmtNum(totals.in)}/${fmtNum(totals.out)}`} sub="soma sobre runs" />
      </div>

      <section className="overflow-hidden rounded-lg border border-line bg-panel">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">operador · tudo</p>
            <h3 className="text-sm font-semibold">Partidas</h3>
          </div>
          <small className="font-mono text-[10.5px] text-faint">clique para abrir na camada Partida</small>
        </div>
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="border-b border-line text-left font-mono text-[10px] uppercase tracking-wider text-faint">
              <th className="px-3 py-2 font-medium"></th>
              <th className="px-3 py-2 font-medium">run / modelo</th>
              <th className="px-3 py-2 font-medium">resultado</th>
              <th className="px-3 py-2 text-right font-medium">plies</th>
              <th className="px-3 py-2 text-right font-medium">calls</th>
              <th className="px-3 py-2 text-right font-medium">tokens i/o</th>
              <th className="px-3 py-2 text-right font-medium">duração</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              const s = runStats(r);
              const ep = lastEp(r);
              return (
                <tr
                  key={r.id}
                  tabIndex={0}
                  role="button"
                  aria-label={`Abrir partida ${r.experiment}`}
                  onClick={() => onOpen(r.id)}
                  onKeyDown={(e) => e.key === "Enter" && onOpen(r.id)}
                  className="cursor-pointer border-b border-line last:border-0 hover:bg-panel2"
                >
                  <td className="px-3 py-2"><StatusPill run={r} /></td>
                  <td className="px-3 py-2">
                    <div className="truncate">{r.experiment.slice(0, 36)}</div>
                    <div className="font-mono text-[10.5px] text-faint">{r.id.slice(4, 14)} · {modelName(r)}</div>
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px]">
                    {ep ? (
                      <span className={ep.result === "checkmate" ? "text-err" : ep.result === "capped" || ep.result === "in_progress" ? "text-warn" : "text-ok"}>
                        {ep.result === "in_progress" ? "ao vivo" : ep.result}{ep.winner ? ` · ${ep.winner}` : ""}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-[11.5px]">{s.plies}</td>
                  <td className="px-3 py-2 text-right font-mono text-[11.5px]">{s.calls}</td>
                  <td className="px-3 py-2 text-right font-mono text-[11.5px]">{fmtNum(s.tokensIn)}/{fmtNum(s.tokensOut)}</td>
                  <td className="px-3 py-2 text-right font-mono text-[11.5px] text-muted">{fmtDur(r.startedAt, r.finishedAt)}</td>
                </tr>
              );
            })}
            {runs.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-muted">nenhuma partida no recorte</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <div className="grid gap-3.5 lg:grid-cols-2">
        <section className="rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-4 py-2.5">
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">distribuição</p>
            <h3 className="text-sm font-semibold">Lances por experimento</h3>
          </div>
          <div className="px-3 py-2">
            {exp.x.length > 0 ? (
              <UPlotChart x={exp.x} ys={exp.ys} series={SERIES_PLIES} yLabel="plies" />
            ) : (
              <div className="py-10 text-center text-muted">sem dados</div>
            )}
            <div className="px-1 pb-2 pt-1 font-mono text-[10px] text-faint">
              {byExp.map(([k]) => k).join(" · ")}
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-4 py-2.5">
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">consumo</p>
            <h3 className="text-sm font-semibold">Tokens por run (in+out)</h3>
          </div>
          <div className="px-3 py-2">
            {tok.x.length > 0 ? (
              <UPlotChart x={tok.x} ys={tok.ys} series={SERIES_TOKENS} yLabel="tokens" />
            ) : (
              <div className="py-10 text-center text-muted">sem dados</div>
            )}
            <div className="px-1 pb-2 pt-1 font-mono text-[10px] text-faint">
              {byTok.map((d) => d.id).join(" · ")}
            </div>
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-line bg-panel">
        <div className="border-b border-line px-4 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-faint">ritmo</p>
          <h3 className="text-sm font-semibold">Latência de decisão p50/p95 por run (s)</h3>
        </div>
        <table className="w-full text-[12px]">
          <tbody>
            {latBands.map((b) => (
              <tr key={b.id} className="border-b border-line last:border-0">
                <td className="w-28 px-4 py-1.5 font-mono text-[11px] text-muted">{b.id}</td>
                <td className="px-3 py-1.5">
                  <div className="relative h-3 w-full rounded bg-panel2">
                    <div className="absolute inset-y-0 rounded bg-info/30" style={{ width: `${Math.min(100, (b.p95 / 150) * 100)}%` }} />
                    <div className="absolute inset-y-0 rounded bg-info" style={{ width: `${Math.min(100, (b.p50 / 150) * 100)}%` }} />
                  </div>
                </td>
                <td className="w-36 px-3 py-1.5 text-right font-mono text-[11px]">
                  p50 {b.p50.toFixed(1)}s · p95 {b.p95.toFixed(1)}s
                </td>
              </tr>
            ))}
            {latBands.length === 0 && <tr><td className="px-4 py-8 text-center text-muted">sem dados de latência</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
