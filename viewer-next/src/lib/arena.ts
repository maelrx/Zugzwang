export interface ProviderModel { id: string; label: string; validated: boolean; default: boolean; service_tiers?: string[] }
export interface ProviderOption {
  id: string; backend_id: string; label: string; validated: boolean; available?: boolean; unavailable_reason?: string;
  models: ProviderModel[]; efforts: string[]; default_effort: string | null; note: string;
}
export interface MoveRecord {
  ply: number; side: string; actor: string; uci: string; san: string;
  latency_ms?: number | null; tokens_out?: number | null; rounds?: number | null; error?: string | null;
}
export interface ModelProgress {
  turn_id: string; started_at: number; finished_at: number | null;
  status: "running" | "completed" | "failed" | "interrupted";
  phase: string; round: number; max_rounds: number; streaming: boolean;
  summaries: {id: string; round: number; text: string; source: string}[];
  steps: {kind: string; round: number; tool: string | null; ok: boolean | null}[];
}
export interface ArenaGameState {
  model_progress?: ModelProgress | null;
  id: string; created_at: string; setup: Record<string, unknown>;
  status: "human_turn" | "model_thinking" | "finished";
  human_color: "white" | "black"; model_color: "white" | "black";
  fen: string; turn: "white" | "black"; last_uci: string | null; check: boolean;
  moves: MoveRecord[]; thinking: boolean; last_error: string | null;
  result: { score: string; kind: string; winner: string | null } | null;
  positions: ReplayPosition[];
  dests: Record<string, string[]> | null; promotable: string[] | null;
}
export interface GameSummary { analysis?: AnalysisSummary; id: string; created_at: string; status: string; human_color: string; plies: number; result: { score: string; kind: string } | null; setup: Record<string, unknown> }

export const API = "/play/api";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { signal: AbortSignal.timeout(15000), headers: { "Content-Type": "application/json" }, ...init });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(String((body as { detail?: string }).detail ?? "falha na requisição")), { code: (body as { error?: string }).error });
  return body as T;
}


export interface ReplayPosition { ply: number; fen: string; last_uci: string | null; san: string | null; turn: "white" | "black"; check: boolean; fullmove: number }
export interface AnalysisPosition { ply: number; fen: string; depth: number | null; requested_depth: number; cp_white: number | null; mate_white: number | null; best_uci: string | null; best_san: string | null; pv_san: string[]; terminal?: string; winner?: string | null; engine: string }
export interface AnalysisSummary { status: string; depth: number; completed?: number; total?: number }
export interface AnalysisState extends AnalysisSummary { positions: AnalysisPosition[]; error?: string | null; profile?: Record<string, unknown> }
export const analysisLabel = (status: string) => ({complete:"Analisada",running:"Analisando",queued:"Na fila",failed:"Análise interrompida",interrupted:"Retomando",awaiting_finish:"Em andamento",not_started:"Sem análise",unavailable:"Engine indisponível"}[status] ?? "Sem análise");
export function scoreLabel(row?: AnalysisPosition): string {
  if (!row) return "—";
  if (row.mate_white != null) return row.mate_white === 0 ? "Mate" : `${row.mate_white > 0 ? "+" : "−"}M${Math.abs(row.mate_white)}`;
  if (row.cp_white == null) return "—";
  return `${row.cp_white > 0 ? "+" : ""}${(row.cp_white / 100).toFixed(2)}`;
}
export function moveLoss(before: AnalysisPosition | undefined, after: AnalysisPosition | undefined, side: string): number | null {
  if (before?.cp_white == null || after?.cp_white == null) return null;
  return Math.max(0, (before.cp_white - after.cp_white) * (side === "white" ? 1 : -1));
}

export function modelName(value: unknown): string {
  const id = String(value ?? "Modelo");
  return ({"gemini-3.8-flash-low":"Gemini 3.8 Flash", "gemini-3.8-flash-high":"Gemini 3.8 Flash", "muse-spark-1.3-contributor":"Muse Spark 1.3", "muse-spark-1.3-free":"Muse Spark 1.3", "gpt-5.6-luna":"GPT-5.6 Luna", "gpt-6-astra":"GPT-6 Astra"} as Record<string,string>)[id] ?? id;
}
export const providerName = (id: unknown) => ({"antigravity-cli":"Gemini",opencode:"Muse","codex-cli":"Codex"} as Record<string,string>)[String(id)] ?? String(id ?? "Modelo");
export const modelDetail = (id: unknown) => String(id ?? "").replace(/^(gemini-3\.8-flash-|muse-spark-1\.3-)/, "");
