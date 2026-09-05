/**
 * Local in-browser Stockfish for VISUALIZATION ONLY.
 *
 * This module is viewer-only: it never feeds the official analysis pipeline
 * (scripts/analyze_deep.py + metric_observations). Scores shown here are a
 * realtime reading aid, not evidence.
 *
 * Protocol discipline (WASM engines wedge on misuse): every new search is
 * serialized as stop → position → go; options are only set while idle.
 */

export type Strength =
  | { mode: "full" }
  | { mode: "elo"; elo: number }
  | { mode: "skill"; skill: number };

export interface EngineOptions {
  /** search depth per position (default 18) */
  depth: number;
  /** worker threads (default 2; single-thread flavor ignores it) */
  threads: number;
  /** hash in MB (default 1024; keep modest — browser tabs OOM easily) */
  hashMb: number;
  strength: Strength;
}

export const DEFAULT_OPTIONS: EngineOptions = {
  depth: 18,
  threads: 2,
  // Modest default: browser tabs OOM easily with big tables, and a wedged
  // worker looks exactly like "stops working after a few moves".
  hashMb: 256,
  strength: { mode: "full" },
};

export interface EngineScore {
  depth: number;
  /** centipawns from White's perspective (null when mate announced) */
  cpWhite: number | null;
  /** mate in N (from White's perspective: +N white mates, -N black mates) */
  mateWhite: number | null;
  bestmove: string | null;
}

export type ScoreCallback = (score: EngineScore, fen: string) => void;

const SINGLE = "/engine/stockfish-18-lite-single.js";
const MULTI = "/engine/stockfish-18-lite.js";

function flavor(): { file: string; threaded: boolean } {
  if (typeof self !== "undefined" && (self as { crossOriginIsolated?: boolean }).crossOriginIsolated === true) {
    return { file: MULTI, threaded: true };
  }
  return { file: SINGLE, threaded: false };
}

export interface LocalEngine {
  readonly threaded: boolean;
  readonly flavor: string;
  analyze: (fen: string, sideToMove: "w" | "b") => void;
  stop: () => void;
  /** Clear transposition table between games (never between moves). */
  newGame: () => void;
  applyOptions: (opts: EngineOptions) => void;
  dispose: () => void;
  /** Counters for the diagnostics panel. */
  stats: () => { sent: number; received: number; errors: number; lastMsgAt: number | null; lastMsgKind: string };
}

export function createLocalEngine(
  initial: EngineOptions,
  onScore: ScoreCallback,
  onEvent?: (kind: "uciok" | "ready" | "error" | "message", detail?: string) => void,
): LocalEngine {
  const { file, threaded } = flavor();
  const worker = new Worker(file);
  let disposed = false;
  let idle = false;
  // A search is in flight between our `go` and the engine's `bestmove`.
  // Because commands are processed in order, any `bestmove` arriving after
  // we issued a NEW analyze() necessarily belongs to the superseded search:
  // `discarding` drops that stale batch (including its trailing bestmove)
  // so an old result can never overwrite the new position's bar.
  let searchActive = false;
  let discarding = false;
  let pendingOptions: EngineOptions | null = null;
  let currentFen = "";
  let currentSide: "w" | "b" = "w";
  let lastDepth = 0;
  let lastCp: number | null = null;
  let lastMate: number | null = null;
  let lastBest: string | null = null;
  let currentDepth = initial.depth;
  let sent = 0;
  let received = 0;
  let handlerErrors = 0;
  let lastMsgAt: number | null = null;
  let lastMsgKind = "—";

  const send = (cmd: string) => {
    if (disposed) return;
    sent++;
    worker.postMessage(cmd);
  };

  const pushOptions = (opts: EngineOptions) => {
    if (threaded) send(`setoption name Threads value ${opts.threads}`);
    send(`setoption name Hash value ${opts.hashMb}`);
    const s = opts.strength;
    if (s.mode === "full") {
      send("setoption name UCI_LimitStrength value false");
    } else if (s.mode === "elo") {
      send("setoption name UCI_LimitStrength value true");
      send(`setoption name UCI_Elo value ${s.elo}`);
    } else {
      send("setoption name UCI_LimitStrength value false");
      send(`setoption name Skill Level value ${s.skill}`);
    }
  };

  worker.onmessage = (e: MessageEvent) => {
    received++;
    lastMsgAt = Date.now();
    try {
      handleLine(typeof e.data === "string" ? e.data : "");
    } catch (err) {
      handlerErrors++;
      onEvent?.("error", `handler: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  function handleLine(line: string): void {
    lastMsgKind = line.slice(0, 24) || "(vazio)";
    onEvent?.("message");
    if (line === "uciok") {
      onEvent?.("uciok");
      pushOptions(initial);
      send("isready");
      return;
    }
    if (line === "readyok") {
      idle = true;
      onEvent?.("ready");
      if (pendingOptions) {
        const o = pendingOptions;
        pendingOptions = null;
        applyOptions(o);
      }
      return;
    }
    const m = line.match(/info depth (\d+).*?\bscore (cp (-?\d+)|mate (-?\d+))/)
    if (m) {
      if (discarding) return;
      const depth = +m[1];
      if (depth < lastDepth) return;
      lastDepth = depth;
      const sign = currentSide === "w" ? 1 : -1;
      if (m[3] !== undefined) {
        lastCp = sign * +m[3];
        lastMate = null;
      } else {
        lastCp = null;
        lastMate = sign * +m[4];
      }
      onScore({ depth, cpWhite: lastCp, mateWhite: lastMate, bestmove: lastBest }, currentFen);
      return;
    }
    const b = line.match(/^bestmove (\S+)/);
    if (b) {
      searchActive = false;
      if (discarding) {
        // trailing bestmove of the superseded search: drop it, resume live
        discarding = false;
        return;
      }
      lastBest = b[1];
      idle = true;
      onScore({ depth: lastDepth, cpWhite: lastCp, mateWhite: lastMate, bestmove: lastBest }, currentFen);
    }
  };

  worker.onerror = (ev: ErrorEvent) => {
    searchActive = false;
    discarding = false;
    idle = true;
    onEvent?.("error", ev.message || "worker error");
    onScore({ depth: 0, cpWhite: null, mateWhite: null, bestmove: null }, currentFen);
  };

  send("uci");

  function analyze(fen: string, sideToMove: "w" | "b"): void {
    if (disposed) return;
    if (searchActive) {
      // a previous search is still producing output: its trailing messages
      // (up to and including its bestmove) belong to the old position
      discarding = true;
    }
    send("stop");
    currentFen = fen;
    currentSide = sideToMove;
    lastDepth = 0;
    lastCp = null;
    lastMate = null;
    lastBest = null;
    send(`position fen ${fen}`);
    send(`go depth ${currentDepth}`);
    searchActive = true;
    idle = false;
  }

  function newGame(): void {
    if (disposed) return;
    send("stop");
    send("ucinewgame");
    searchActive = false;
    discarding = false;
  }

  function applyOptions(opts: EngineOptions): void {
    currentDepth = opts.depth;
    if (!idle) {
      // never reconfigure mid-search: queue for when the engine idles
      pendingOptions = opts;
      send("stop");
      return;
    }
    send("stop");
    pushOptions(opts);
    send("isready");
    idle = false;
  }

  return {
    threaded,
    flavor: file.split("/").pop() ?? file,
    analyze,
    stop: () => send("stop"),
    newGame,
    applyOptions,
    stats: () => ({ sent, received, errors: handlerErrors, lastMsgAt, lastMsgKind }),
    dispose: () => {
      disposed = true;
      try {
        worker.postMessage("quit");
      } catch {
        /* already gone */
      }
      worker.terminate();
    },
  };
}

/** Logistic win-pct for the eval bar (white perspective). */
export function winPct(cpWhite: number | null, mateWhite: number | null): number {
  if (mateWhite !== null) return mateWhite > 0 ? 100 : 0;
  if (cpWhite === null) return 50;
  return 100 / (1 + Math.exp(-0.004 * cpWhite));
}

export function scoreLabel(cpWhite: number | null, mateWhite: number | null): string {
  if (mateWhite !== null) return mateWhite > 0 ? `M${Math.abs(mateWhite)}` : `-M${Math.abs(mateWhite)}`;
  if (cpWhite === null) return "…";
  const pawns = cpWhite / 100;
  return (pawns > 0 ? "+" : "") + (Math.abs(pawns) >= 20 ? pawns.toFixed(0) : pawns.toFixed(1));
}
