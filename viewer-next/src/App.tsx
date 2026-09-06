import { useMemo, useState } from "react";
import { useSnapshot } from "@/lib/useSnapshot";
import { modelName } from "@/lib/types";
import { RunsOverview } from "@/components/RunsOverview";
import { GameView } from "@/components/GameView";
import { DeepView } from "@/components/DeepView";

type Layer = "L0" | "L1" | "L2";

const HINTS: Record<Layer, string> = {
  L0: "visão de operador: todas as partidas, sinais vitais",
  L1: "uma partida: replay, ritmo e consumo por lance",
  L2: "drill-down: configuração, eventos brutos, proveniência",
};

export default function App() {
  const { snap, loading, error, refreshedAt, reload } = useSnapshot(15000);
  const [layer, setLayer] = useState<Layer>("L0");
  const [runId, setRunId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const runs = useMemo(() => snap?.runs ?? [], [snap]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return runs;
    return runs.filter((r) =>
      [r.id, r.experiment, r.conditionId ?? "", modelName(r), r.status, ...(r.tags ?? [])]
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  }, [runs, query]);

  const current = runs.find((r) => r.id === runId) ?? null;

  const go = (l: Layer, id?: string) => {
    if (id) setRunId(id);
    if (l !== "L0" && !id && !runId && runs.length) setRunId(runs[0].id);
    setLayer(l);
  };

  const tab = (l: Layer, label: string) => (
    <button
      onClick={() => go(l)}
      aria-pressed={layer === l}
      className={
        "rounded px-3.5 py-1.5 text-[12.5px] transition-colors " +
        (layer === l ? "bg-paper font-semibold text-ink" : "text-muted hover:text-paper")
      }
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-ink/90 px-5 py-2 backdrop-blur">
        <div className="flex items-baseline gap-2.5 whitespace-nowrap">
          <strong className="text-[15px] tracking-tight">Zugzwang Match Desk</strong>
          <span className="font-mono text-[10.5px] text-faint">observabilidade · somente leitura</span>
        </div>
        <nav className="flex gap-0.5 rounded-md border border-line bg-panel p-0.5" aria-label="Camada de observabilidade">
          {tab("L0", "Operação")}
          {tab("L1", "Partida")}
          {tab("L2", "Profundo")}
        </nav>
        <span className="hidden text-[11.5px] text-faint md:inline">{HINTS[layer]}</span>
        <div className="flex-1" />
        <div className="text-right font-mono text-[10.5px] leading-4 text-faint">
          <div>snapshot {(refreshedAt ? new Date(refreshedAt) : null)?.toISOString().slice(11, 19) ?? "—"} UTC</div>
          <button onClick={reload} className="text-accent hover:underline">recarregar dados</button>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[288px_1fr]">
        <aside className="flex flex-col border-line lg:sticky lg:top-[49px] lg:h-[calc(100vh-49px)] lg:border-r">
          <div className="p-3.5 pb-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="filtrar run, modelo, condição…"
              className="w-full rounded border border-line bg-panel px-2.5 py-1.5 text-[13px] placeholder:text-faint"
              aria-label="Filtrar partidas"
            />
          </div>
          <div className="flex justify-between px-4 pb-2 font-mono text-[10.5px] text-faint">
            <span>partidas</span>
            <span>{filtered.length}</span>
          </div>
          <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-3">
            {filtered.map((r) => (
              <button
                key={r.id}
                onClick={() => go("L1", r.id)}
                className={
                  "block w-full rounded px-2.5 py-2 text-left " +
                  (r.id === runId ? "border border-faint/60 bg-panel" : "border border-transparent hover:bg-panel")
                }
              >
                <div className="flex items-center gap-2">
                  {r.status === "RUNNING" ? (
                    <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-warn" title="live" />
                  ) : (
                    <span className={"size-1.5 shrink-0 rounded-full " + (r.status === "COMPLETED" ? "bg-ok" : "bg-err")} />
                  )}
                  <span className="truncate text-[13px]">{r.experiment.slice(0, 28)}</span>
                </div>
                <div className="mt-0.5 truncate font-mono text-[10.5px] text-faint">
                  {r.id.slice(4, 16)} · {modelName(r)}
                </div>
              </button>
            ))}
            {filtered.length === 0 && !loading && (
              <div className="px-3 py-8 text-center text-[12px] text-muted">nenhuma partida</div>
            )}
          </div>
        </aside>

        <main className="min-w-0 p-4 pb-16 md:p-5">
          {loading && <div className="py-20 text-center text-muted">carregando snapshot…</div>}
          {error && (
            <div className="py-20 text-center">
              <p className="text-err">falha ao carregar data.json: {error}</p>
              <p className="mt-2 text-[12px] text-muted">
                rode <code className="font-mono text-paper">uv run python scripts/build_readonly_viewer.py --workspace .</code> e
                confira se o servidor estático (porta 4173) está de pé.
              </p>
            </div>
          )}
          {!loading && !error && layer === "L0" && (
            <RunsOverview runs={filtered} onOpen={(id) => go("L1", id)} />
          )}
          {!loading && !error && layer !== "L0" && current && (
            layer === "L1"
              ? <GameView key={current.id} run={current} onBack={() => setLayer("L0")} onDeep={() => setLayer("L2")} />
              : <DeepView run={current} onBack={() => setLayer("L1")} />
          )}
          {!loading && !error && layer !== "L0" && !current && (
            <div className="py-20 text-center text-muted">selecione uma partida na barra lateral</div>
          )}
        </main>
      </div>
    </div>
  );
}
