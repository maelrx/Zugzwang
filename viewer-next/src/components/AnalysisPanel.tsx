import { useMemo } from "react";
import type { Episode, Metric } from "@/lib/types";

interface Row {
  n: string;
  san: string;
  evalBefore: number | null;
  cpl: number | null;
  cls: string | null;
  best: string | null;
  agree: boolean | null;
  ply: number;
}

const CLS_STYLE: Record<string, string> = {
  best_or_good: "text-ok",
  inaccuracy: "text-info",
  mistake: "text-warn",
  blunder: "text-err",
  none: "text-faint",
};

const CLS_LABEL: Record<string, string> = {
  best_or_good: "preciso",
  inaccuracy: "imprecisão",
  mistake: "erro",
  blunder: "brinde",
  none: "—",
};

/**
 * Official post-hoc analysis showcase (DB-backed, versioned evaluator).
 * Renders ONLY when metric_observations exist for the episode — i.e. only
 * real complete backend analysis ever appears here. The in-browser live
 * engine has no code path into this panel.
 */
export function AnalysisPanel({ episode, metrics }: { episode: Episode; metrics: Metric[] }) {
  const rows = useMemo<Row[] | null>(() => {
    const mine = (metrics ?? []).filter((m) => m.episodeId === episode.id);
    if (mine.length === 0) return null;
    const byStep = new Map<string, Metric[]>();
    for (const m of mine) {
      if (!m.stepId) continue;
      const arr = byStep.get(m.stepId) ?? [];
      arr.push(m);
      byStep.set(m.stepId, arr);
    }
    const get = (stepId: string, id: string) => byStep.get(stepId)?.find((m) => m.metric === id);
    const out: Row[] = [];
    for (const mv of episode.moves ?? []) {
      if (mv.actorKind !== "Model") continue;
      const cpl = get(mv.stepId, "chess.cpl")?.valueNum ?? null;
      const cls = get(mv.stepId, "chess.move_class")?.valueText ?? null;
      const best = get(mv.stepId, "chess.engine_best_move")?.valueText ?? null;
      const agr = get(mv.stepId, "chess.best_move_agreement")?.valueNum;
      out.push({
        n: `${Math.floor((mv.ply - 1) / 2) + 1}${mv.side === "White" ? "." : "…"}`,
        san: mv.san ?? mv.display,
        evalBefore: get(mv.stepId, "chess.engine_score_before")?.valueNum ?? null,
        cpl: typeof cpl === "number" ? cpl : null,
        cls,
        best,
        agree: typeof agr === "number" ? agr === 1 : null,
        ply: mv.ply,
      });
    }
    return out.length > 0 ? out : null;
  }, [episode, metrics]);

  const stats = useMemo(() => {
    if (!rows) return null;
    const cpls = rows.map((r) => r.cpl).filter((v): v is number => typeof v === "number");
    const agr = rows.filter((r) => r.agree === true).length;
    const agrN = rows.filter((r) => r.agree !== null).length;
    const count = (c: string) => rows.filter((r) => r.cls === c).length;
    return {
      n: rows.length,
      avgCpl: cpls.length ? cpls.reduce((a, b) => a + b, 0) / cpls.length : null,
      agrPct: agrN ? Math.round((agr / agrN) * 100) : null,
      blunders: count("blunder"),
      mistakes: count("mistake"),
      inacc: count("inaccuracy"),
    };
  }, [rows]);

  if (!rows || !stats) {
    return (
      <section className="rounded-lg border border-line bg-panel">
        <div className="border-b border-line px-4 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-faint">oficial · pós-jogo</p>
          <h3 className="text-sm font-semibold">Análise profunda</h3>
        </div>
        <div className="py-10 text-center text-[12.5px] text-muted">
          sem análise oficial ainda — roda <code className="font-mono text-paper">scripts/analyze_deep.py</code>
        </div>
      </section>
    );
  }

  const fmtEv = (v: number | null) => {
    if (v === null) return "—";
    const c = Math.max(-2000, Math.min(2000, v)) / 100;
    return (c > 0 ? "+" : "") + (Math.abs(c) >= 20 ? c.toFixed(0) : c.toFixed(1));
  };

  return (
    <section className="rounded-lg border border-line bg-panel">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-faint">oficial · pós-jogo · depth 20</p>
          <h3 className="text-sm font-semibold">Análise profunda</h3>
        </div>
        <small className="font-mono text-[10.5px] text-faint">só análise real do backend</small>
      </div>

      <div className="grid grid-cols-3 gap-2 border-b border-line px-4 py-3 text-center md:grid-cols-6">
        <div><div className="font-mono text-[9.5px] uppercase tracking-wider text-faint">lances</div><div className="text-lg font-semibold">{stats.n}</div></div>
        <div><div className="font-mono text-[9.5px] uppercase tracking-wider text-faint">cpl médio</div><div className="text-lg font-semibold">{stats.avgCpl !== null ? stats.avgCpl.toFixed(0) : "—"}</div></div>
        <div><div className="font-mono text-[9.5px] uppercase tracking-wider text-faint">acordo SF</div><div className="text-lg font-semibold">{stats.agrPct !== null ? `${stats.agrPct}%` : "—"}</div></div>
        <div><div className="font-mono text-[9.5px] uppercase tracking-wider text-faint">brindes</div><div className={`text-lg font-semibold ${stats.blunders ? "text-err" : ""}`}>{stats.blunders}</div></div>
        <div><div className="font-mono text-[9.5px] uppercase tracking-wider text-faint">erros</div><div className={`text-lg font-semibold ${stats.mistakes ? "text-warn" : ""}`}>{stats.mistakes}</div></div>
        <div><div className="font-mono text-[9.5px] uppercase tracking-wider text-faint">imprecisões</div><div className="text-lg font-semibold">{stats.inacc}</div></div>
      </div>

      <div className="max-h-80 overflow-y-auto">
        <table className="w-full font-mono text-[11.5px]">
          <thead className="sticky top-0 bg-panel">
            <tr className="border-b border-line text-left text-[9.5px] uppercase tracking-wider text-faint">
              <th className="px-3 py-1.5 font-medium">#</th>
              <th className="px-2 py-1.5 font-medium">lance</th>
              <th className="px-2 py-1.5 text-right font-medium">eval</th>
              <th className="px-2 py-1.5 text-right font-medium">cpl</th>
              <th className="px-2 py-1.5 font-medium">classe</th>
              <th className="px-2 py-1.5 font-medium">engine</th>
              <th className="px-3 py-1.5 text-center font-medium">=</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.ply} className="border-b border-line last:border-0 hover:bg-panel2">
                <td className="px-3 py-1 text-faint">{r.n}</td>
                <td className="px-2 py-1 text-paper">{r.san}</td>
                <td className="px-2 py-1 text-right text-muted">{fmtEv(r.evalBefore)}</td>
                <td className="px-2 py-1 text-right text-muted">{r.cpl !== null ? r.cpl.toFixed(0) : "—"}</td>
                <td className={`px-2 py-1 ${r.cls ? CLS_STYLE[r.cls] ?? "" : "text-faint"}`}>
                  {r.cls ? CLS_LABEL[r.cls] ?? r.cls : "—"}
                </td>
                <td className="px-2 py-1 text-faint">{r.best ?? "—"}</td>
                <td className="px-3 py-1 text-center">{r.agree === null ? <span className="text-faint">—</span> : r.agree ? <span className="text-ok">✓</span> : <span className="text-err">✗</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
