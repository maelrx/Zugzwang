/** Snapshot shapes produced by scripts/build_readonly_viewer.py (read-only bridge). */

export interface ProviderStats {
  attempts: number;
  status: "ok" | "repaired" | "failed" | "timeout_unknown";
  latencyMs: number;
  tokensIn: number | null;
  tokensOut: number | null;
}

export interface Move {
  ply: number;
  side: "White" | "Black";
  moveNumber: number;
  uci: string | null;
  san: string | null;
  display: string;
  kind?: string | null;
  actor: string;
  actorKind: "Model" | "Stockfish" | "Random" | "Opponent" | "Model opponent";
  policy?: Record<string, unknown> | null;
  stepId: string;
  fenAfter: string | null;
  terminal: boolean;
  committedAt: string | null;
  provider?: ProviderStats | null;
}

export interface Position {
  ply: number;
  fen: string | null;
  moves: string[];
  terminal: boolean;
}

export type RunStatus = "COMPLETED" | "RUNNING" | "FAILED" | "CANCELLED" | string;

export interface Episode {
  id: string;
  ordinal: number;
  status: RunStatus;
  outcome: string | null;
  stepsCommitted: number;
  stepsFailed: number;
  result: "checkmate" | "stalemate" | "capped" | "completed" | "failed" | "in_progress" | string;
  winner: "White" | "Black" | null;
  positions: Position[];
  moves: Move[];
}

export interface ProviderSummary {
  calls: number;
  failures: number;
  tokens: { input: number; output: number };
  costStatus: string;
  costEntries: unknown[];
}

export interface PlayerInfo {
  side: string;
  model?: Record<string, unknown> | null;
  policy?: Record<string, unknown> | null;
}

export interface Metric {
  id: string | null;
  metric: string | null;
  version: string | null;
  valueNum: number | null;
  valueText: string | null;
  unit: string | null;
  dimensions: Record<string, unknown>;
  evaluator: string | null;
  episodeId: string | null;
  stepId: string | null;
}

export interface EventRow {
  type: string;
  at: string | null;
  payload: Record<string, unknown>;
  artifactCount: number;
}

export interface Run {
  id: string;
  status: RunStatus;
  conditionId: string | null;
  experiment: string;
  tags: string[];
  protocolHash: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  declaredAssistance: string | null;
  effectiveAssistance: string | null;
  players: PlayerInfo[];
  model: Record<string, unknown> | null;
  opponents: PlayerInfo[];
  task: Record<string, unknown>;
  budget: Record<string, unknown>;
  provider: ProviderSummary;
  episodes: Episode[];
  metrics: Metric[];
  events: EventRow[];
}

export interface Snapshot {
  generatedAt: string;
  workspace: string;
  readOnly: boolean;
  runs: Run[];
}

/** Derived per-model-move series used by charts. */
export interface DecisionPoint {
  ply: number;
  san: string;
  latencyMs: number;
  attempts: number;
  status: ProviderStats["status"];
  tokensIn: number;
  tokensOut: number;
  cumIn: number;
  cumOut: number;
  timeSec: number | null;
}

export function modelDecisions(episode: Episode): DecisionPoint[] {
  const out: DecisionPoint[] = [];
  let cumIn = 0;
  let cumOut = 0;
  let t0: number | null = null;
  for (const m of episode.moves ?? []) {
    if (m.actorKind !== "Model" || !m.provider) continue;
    if (t0 === null && m.committedAt) t0 = Date.parse(m.committedAt);
    const t = m.committedAt ? Date.parse(m.committedAt) : null;
    cumIn += m.provider.tokensIn ?? 0;
    cumOut += m.provider.tokensOut ?? 0;
    out.push({
      ply: m.ply,
      san: m.san ?? m.display,
      latencyMs: m.provider.latencyMs,
      attempts: m.provider.attempts,
      status: m.provider.status,
      tokensIn: m.provider.tokensIn ?? 0,
      tokensOut: m.provider.tokensOut ?? 0,
      cumIn,
      cumOut,
      timeSec: t !== null && t0 !== null ? (t - t0) / 1000 : null,
    });
  }
  return out;
}

export function runStats(run: Run) {
  const episodes = run.episodes ?? [];
  const moves = episodes.flatMap((e) => e.moves ?? []);
  const modelMoves = moves.filter((m) => m.actorKind === "Model");
  const provs = modelMoves
    .map((m) => m.provider)
    .filter((p): p is ProviderStats => Boolean(p));
  const latencies = provs.map((p) => p.latencyMs).filter((v) => v != null);
  return {
    episodes,
    moves,
    plies: moves.length,
    modelMoves: modelMoves.length,
    calls: provs.length,
    attempts: provs.reduce((s, p) => s + p.attempts, 0),
    repaired: provs.filter((p) => p.status === "repaired").length,
    timeouts: provs.filter((p) => p.status === "timeout_unknown").length,
    tokensIn:
      provs.reduce((s, p) => s + (p.tokensIn ?? 0), 0) ||
      run.provider?.tokens?.input ||
      0,
    tokensOut:
      provs.reduce((s, p) => s + (p.tokensOut ?? 0), 0) ||
      run.provider?.tokens?.output ||
      0,
    latencies,
  };
}

export function modelName(run: Run): string {
  const m = run.model as { model?: string } | null;
  return m?.model ?? "—";
}
