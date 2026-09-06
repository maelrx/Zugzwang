import { useMemo } from "react";
import type { Run } from "@/lib/types";
import { runStats } from "@/lib/types";
import { fmtNum, fmtMs, fmtDur } from "@/lib/format";

function Fact({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="font-mono text-[10px] uppercase tracking-wider text-faint">{label}</div>
      <div className={`mt-0.5 truncate text-[12.5px] ${mono ? "font-mono text-[11.5px]" : ""}`} title={value}>{value}</div>
    </div>
  );
}

export function DeepView({ run, onBack }: { run: Run; onBack: () => void }) {
  const s = useMemo(() => runStats(run), [run]);
  const events = useMemo(() => [...(run.events ?? [])].reverse().slice(0, 160), [run]);

  const evTone = (t: string) =>
    /failed|illegal|timeout/.test(t)
      ? "text-err"
      : /completed|committed/.test(t)
        ? "text-muted"
        : "text-info";

  return (
    <div className="space-y-3.5">
      <div className="flex flex-wrap items-center gap-2.5">
        <h2 className="text-lg font-semibold">Profundo · {run.experiment}</h2>
        <span className="font-mono text-[11px] text-muted">{run.id}</span>
        <div className="flex-1" />
        <button onClick={onBack} className="rounded-md border border-line bg-panel px-3 py-1.5 text-[12.5px] hover:border-faint">
          ← partida
        </button>
      </div>

      <section className="rounded-lg border border-line bg-panel">
        <div className="border-b border-line px-4 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-faint">proveniência</p>
          <h3 className="text-sm font-semibold">Identidade do run</h3>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2.5 p-4 md:grid-cols-4">
          <Fact label="run" value={run.id} />
          <Fact label="condição" value={run.conditionId ?? "—"} />
          <Fact label="protocol hash" value={run.protocolHash ?? "—"} />
          <Fact label="assistência declarada→efetiva" value={`${run.declaredAssistance ?? "—"} → ${run.effectiveAssistance ?? "—"}`} mono={false} />
          <Fact label="janela (UTC)" value={`${run.startedAt?.slice(11, 19) ?? "—"} → ${run.finishedAt?.slice(11, 19) ?? "—"}`} />
          <Fact label="duração" value={fmtDur(run.startedAt, run.finishedAt)} mono={false} />
          <Fact label="snapshot" value="viewer/data.json" />
          <Fact label="custo" value={run.provider.costStatus} mono={false} />
        </div>
      </section>

      <div className="grid gap-3.5 lg:grid-cols-2">
        <section className="rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-4 py-2.5">
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">jogadores</p>
            <h3 className="text-sm font-semibold">Modelo & oponente</h3>
          </div>
          <div className="space-y-3 p-4">
            <div>
              <div className="font-mono text-[10px] text-faint">white/decision-maker</div>
              <pre className="mt-1 overflow-x-auto rounded bg-panel2 p-2 font-mono text-[10.5px] leading-5 text-muted">{JSON.stringify(run.model ?? run.players?.[0], null, 1)}</pre>
            </div>
            <div>
              <div className="font-mono text-[10px] text-faint">black/opponent policy</div>
              <pre className="mt-1 overflow-x-auto rounded bg-panel2 p-2 font-mono text-[10.5px] leading-5 text-muted">{JSON.stringify(run.opponents?.[0]?.policy ?? run.opponents?.[0], null, 1)}</pre>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-4 py-2.5">
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">configuração efetiva</p>
            <h3 className="text-sm font-semibold">Task (redigido)</h3>
          </div>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all p-4 font-mono text-[10.5px] leading-5 text-muted">{JSON.stringify(run.task, null, 1)}</pre>
        </section>
      </div>

      <section className="rounded-lg border border-line bg-panel">
        <div className="border-b border-line px-4 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-faint">sinais operacionais</p>
          <h3 className="text-sm font-semibold">Resumo técnico</h3>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2.5 p-4 md:grid-cols-5">
          <Fact label="lances / episódios" value={`${s.plies} / ${s.episodes.length}`} mono={false} />
          <Fact label="calls ok / attempts" value={`${s.calls} / ${s.attempts}`} mono={false} />
          <Fact label="latência média" value={s.latencies.length ? fmtMs(s.latencies.reduce((a, b) => a + b, 0) / s.latencies.length) : "—"} mono={false} />
          <Fact label="latência p95" value={s.latencies.length ? fmtMs([...s.latencies].sort((a, b) => a - b)[Math.floor(s.latencies.length * 0.95)]) : "—"} mono={false} />
          <Fact label="tokens in/out" value={`${fmtNum(s.tokensIn)} / ${fmtNum(s.tokensOut)}`} mono={false} />
        </div>
      </section>

      <section className="rounded-lg border border-line bg-panel">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">linha do tempo</p>
            <h3 className="text-sm font-semibold">Eventos brutos</h3>
          </div>
          <small className="font-mono text-[10.5px] text-faint">{(run.events ?? []).length} eventos · 160 recentes</small>
        </div>
        <div className="max-h-96 overflow-y-auto font-mono text-[11px]">
          {events.map((e, i) => (
            <div key={i} className="grid grid-cols-[70px_230px_1fr] gap-2.5 border-b border-line px-3 py-[3px] last:border-0 hover:bg-panel2">
              <span className="text-faint">{e.at?.slice(11, 19) ?? "—"}</span>
              <span className={evTone(e.type)}>{e.type}</span>
              <span className="truncate text-muted">{JSON.stringify(e.payload).slice(0, 130)}</span>
            </div>
          ))}
          {events.length === 0 && <div className="py-10 text-center text-muted">sem eventos</div>}
        </div>
      </section>

      {(run.metrics?.length ?? 0) > 0 && (
        <section className="rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-4 py-2.5">
            <p className="font-mono text-[10px] uppercase tracking-widest text-faint">pós-jogo</p>
            <h3 className="text-sm font-semibold">Métricas de avaliadores</h3>
          </div>
          <div className="max-h-72 overflow-y-auto font-mono text-[11px]">
            {run.metrics.slice(0, 120).map((m, mi) => (
              <div key={m.id ?? `metric-${mi}`} className="grid grid-cols-[190px_110px_1fr] gap-2.5 border-b border-line px-3 py-[3px] last:border-0">
                <span className="text-info">{m.metric ?? "—"}</span>
                <span className="text-paper">{m.valueNum ?? m.valueText ?? "—"}</span>
                <span className="truncate text-faint">{m.evaluator} {m.stepId ? `· ${m.stepId.slice(0, 12)}` : ""}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
