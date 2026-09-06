import { useEffect, useRef, useState } from "react";
import {
  createLocalEngine,
  winPct,
  scoreLabel,
  DEFAULT_OPTIONS,
  type EngineOptions,
  type EngineScore,
  type LocalEngine,
} from "@/lib/localEngine";

/**
 * Realtime local eval bar (viewer-only, never official analysis).
 * Wraps the board's left edge: white share grows upward from 50%.
 */
export function LiveEval({
  fen,
  gameKey,
  disabled,
}: {
  fen: string | null;
  /** changes when the game/episode changes → clears hash + score */
  gameKey: string;
  disabled?: boolean;
}) {
  const [enabled, setEnabled] = useState(true);
  const [opts, setOpts] = useState<EngineOptions>(DEFAULT_OPTIONS);
  const [showConfig, setShowConfig] = useState(false);
  const [score, setScore] = useState<EngineScore | null>(null);
  const [thinking, setThinking] = useState(false);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [restarts, setRestarts] = useState(0);
  const [autoRestarts, setAutoRestarts] = useState(0);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [diagTick, setDiagTick] = useState(0);
  const engine = useRef<LocalEngine | null>(null);
  const fenRef = useRef<string | null>(null);
  const lastActivity = useRef<number>(Date.now());
  const timer = useRef<number | undefined>(undefined);

  const touch = () => {
    lastActivity.current = Date.now();
  };

  // Lifecycle: one worker per mount (StrictMode remount disposes cleanly).
  // `restarts` lets the user nuke a wedged worker without reloading the page.
  useEffect(() => {
    let eng: LocalEngine | null = null;
    try {
      eng = createLocalEngine(
        opts,
        (s) => {
          touch();
          setScore(s);
          setThinking(false);
          setStatus((prev) => (prev === "error" && s.depth === 0 ? prev : "ready"));
        },
        (kind, detail) => {
          touch();
          if (kind === "error") {
            setEngineError(detail ?? "worker error");
            setStatus("error");
          }
          if (kind === "uciok" || kind === "ready") setEngineError(null);
        },
      );
      engine.current = eng;
    } catch {
      setStatus("error");
    }
    return () => {
      engine.current?.dispose();
      engine.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restarts]);

  useEffect(() => {
    engine.current?.applyOptions(opts);
  }, [opts]);

  // New game: clear hash table and stale score.
  useEffect(() => {
    engine.current?.newGame();
    fenRef.current = null;
    setScore(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameKey]);

  // Analyze current position (debounced) whenever it changes.
  useEffect(() => {
    if (!enabled || disabled || !fen) return;
    if (fen === fenRef.current) return;
    fenRef.current = fen;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const side = fen.split(" ")[1] === "b" ? "b" : "w";
      setScore(null);
      setThinking(true);
      touch();
      engine.current?.analyze(fen, side);
    }, 250);
    return () => window.clearTimeout(timer.current);
  }, [fen, enabled, disabled, restarts]);

  const restartWorker = (auto: boolean) => {
    engine.current?.dispose();
    engine.current = null;
    fenRef.current = null;
    setScore(null);
    setStatus("loading");
    setThinking(false);
    setEngineError(null);
    touch();
    if (auto) setAutoRestarts((n) => n + 1);
    else setRestarts((n) => n + 1);
    // auto path remounts through the same state so the current fen re-analyzes
    if (auto) setRestarts((n) => n + 1);
  };

  // Watchdog: a healthy engine streams *something* (even depth-1) within
  // seconds. Silence >25s while thinking means wedged worker (WASM trap/OOM
  // rarely fires onerror) → auto-restart and resume the current position.
  useEffect(() => {
    if (!enabled || disabled) return;
    const t = window.setInterval(() => {
      if (thinking && Date.now() - lastActivity.current > 25000) {
        restartWorker(true);
      }
    }, 5000);
    return () => window.clearInterval(t);
  }, [enabled, disabled, thinking]);

  // Tick diagnostics clock while the config panel is open.
  useEffect(() => {
    if (!showConfig) return;
    const t = window.setInterval(() => setDiagTick((n) => n + 1), 2000);
    return () => window.clearInterval(t);
  }, [showConfig]);

  const pct = winPct(score?.cpWhite ?? null, score?.mateWhite ?? null);
  const busy = thinking || status === "loading";
  const label =
    status === "error"
      ? "engine off"
      : busy && !score
        ? "…"
        : scoreLabel(score?.cpWhite ?? null, score?.mateWhite ?? null);
  const depthNote =
    score && score.depth > 0 ? `D${score.depth}/${opts.depth}` : `D…/${opts.depth}`;

  const set = <K extends keyof EngineOptions>(k: K, v: EngineOptions[K]) =>
    setOpts((o) => ({ ...o, [k]: v }));

  const num = "w-full rounded border border-line bg-panel2 px-1.5 py-1 font-mono text-[11px]";

  return (
    <div className="flex gap-2">
      <div className="flex w-9 shrink-0 flex-col items-stretch gap-1">
        <div
          className="relative flex-1 overflow-hidden rounded border border-line bg-[#20242c]"
          role="img"
          aria-label={`avaliação local: ${label} para as brancas`}
          title={enabled ? `local engine · ${depthNote} · ${label}` : "engine local desligado"}
        >
          <div
            className="absolute inset-x-0 bottom-0 bg-[#e8e4da] transition-[height] duration-300"
            style={{ height: `${enabled ? pct : 50}%` }}
          />
          <div className="absolute inset-x-0 top-1/2 h-px bg-faint/60" />
          {busy && enabled && (
            <div className="absolute inset-x-0 top-1 flex justify-center">
              <span className="size-1.5 animate-pulse rounded-full bg-accent" />
            </div>
          )}
        </div>
        <div className="text-center font-mono text-[10px] text-muted" title={depthNote}>
          {enabled ? (busy && !score ? depthNote : label) : "off"}
        </div>
        <button
          onClick={() => setEnabled((v) => !v)}
          aria-pressed={enabled}
          title={enabled ? "desligar engine local" : "ligar engine local"}
          className={`rounded border px-1 py-0.5 font-mono text-[10px] ${enabled ? "border-ok/50 text-ok" : "border-line text-faint"}`}
        >
          SF
        </button>
        <button
          onClick={() => setShowConfig((v) => !v)}
          aria-pressed={showConfig}
          title="configurar engine local"
          className="rounded border border-line px-1 py-0.5 font-mono text-[10px] text-muted hover:text-paper"
        >
          ⚙
        </button>
      </div>

      {showConfig && (
        <div className="mb-2 w-44 shrink-0 space-y-2 rounded-md border border-line bg-panel2 p-2.5 text-[11.5px]">
          <p className="font-mono text-[9.5px] uppercase tracking-widest text-faint">engine local · só visual</p>
          <label className="block">
            <span className="text-muted">profundidade ({opts.depth})</span>
            <input type="range" min={6} max={24} value={opts.depth} onChange={(e) => set("depth", +e.target.value)} className="w-full accent-accent" />
          </label>
          <label className="block">
            <span className="text-muted">threads ({opts.threads}){engine.current && !engine.current.threaded ? " · single" : ""}</span>
            <input type="range" min={1} max={8} value={opts.threads} onChange={(e) => set("threads", +e.target.value)} className="w-full accent-accent" />
          </label>
          <label className="block">
            <span className="text-muted">hash MB</span>
            <input type="number" min={16} max={2048} step={16} value={opts.hashMb} onChange={(e) => set("hashMb", Math.max(16, +e.target.value || 16))} className={num} />
          </label>
          <label className="block">
            <span className="text-muted">força</span>
            <select
              value={opts.strength.mode}
              onChange={(e) => {
                const mode = e.target.value as "full" | "elo" | "skill";
                set("strength", mode === "full" ? { mode } : mode === "elo" ? { mode, elo: 1200 } : { mode, skill: 5 });
              }}
              className={num}
            >
              <option value="full">máxima</option>
              <option value="elo">UCI_Elo</option>
              <option value="skill">Skill Level</option>
            </select>
          </label>
          {opts.strength.mode === "elo" && (
            <label className="block">
              <span className="text-muted">UCI_Elo ({opts.strength.elo})</span>
              <input type="range" min={400} max={3000} step={50} value={opts.strength.elo} onChange={(e) => set("strength", { mode: "elo", elo: +e.target.value })} className="w-full accent-accent" />
            </label>
          )}
          {opts.strength.mode === "skill" && (
            <label className="block">
              <span className="text-muted">Skill ({opts.strength.skill})</span>
              <input type="range" min={0} max={20} value={opts.strength.skill} onChange={(e) => set("strength", { mode: "skill", skill: +e.target.value })} className="w-full accent-accent" />
            </label>
          )}
          <button
            onClick={() => restartWorker(false)}
            title="reiniciar o worker (se travar)"
            className="w-full rounded border border-line px-1.5 py-1 font-mono text-[10px] text-muted hover:text-paper"
          >
            ↻ reiniciar engine
          </button>
          <div className="rounded bg-ink p-1.5 font-mono text-[9.5px] leading-4 text-faint">
            {(() => {
              void diagTick;
              const st = engine.current?.stats();
              const ago =
                st?.lastMsgAt == null ? "—" : `${Math.max(0, Math.round((Date.now() - st.lastMsgAt) / 1000))}s atrás`;
              return (
                <>
                  <div>flavor: {engine.current?.flavor ?? "—"}{engine.current && !engine.current.threaded ? " · single" : ""}</div>
                  <div>isolado: {typeof crossOriginIsolated !== "undefined" && crossOriginIsolated ? "sim" : "não"}</div>
                  <div>
                    msgs: {st ? `${st.received}← ${st.sent}→` : "—"} · erros: {st?.errors ?? "—"}
                  </div>
                  <div>última msg: {ago}{st?.lastMsgKind ? ` · ${st.lastMsgKind}` : ""}</div>
                  {engineError ? <div className="text-err">erro: {engineError}</div> : null}
                  {autoRestarts > 0 ? <div className="text-warn">auto-restarts: {autoRestarts}</div> : null}
                </>
              );
            })()}
          </div>
          <p className="font-mono text-[9.5px] leading-4 text-faint">não entra na análise oficial do banco</p>
        </div>
      )}
    </div>
  );
}
