import type { Episode, Run } from "./types.ts";

export type StatusFilter = "all" | "running" | "completed" | "attention";
export type DetailView = "game" | "analysis" | "evidence";
export type Tone = "ok" | "warn" | "err" | "muted" | "info";
export const shortId = (id: string) => id.replace(/^run_/, "").slice(0, 8);
export function modelLabel(run: Run): string {
  const model = run.model?.model ?? run.players?.find(p => p.model)?.model?.model;
  if (typeof model === "string" && model) return model;
  const actor = run.episodes?.flatMap(e => e.moves ?? []).find(m => m.actorKind === "Model")?.actor;
  return actor?.split("/").filter(Boolean).at(-1) || "Modelo não informado";
}
export function experimentLabel(name: string): string {
  if (!name || name === "Zugzwang run") return "Sem identificação de experimento";
  return name.replace(/^local-/, "").replace(/^musespark-1[.-]3-(go|free)-/, "")
    .replace(/single-agent-tree-battery/, "Árvore legal · bateria")
    .replace(/h2-clean-xhigh-triple/, "H2 · Xhigh · novas réplicas")
    .replace(/h2-nocap-xhigh-triple/, "H2 · Xhigh · sem limite de lances")
    .replace(/h3-repro-effort-matrix/, "H3 · níveis de raciocínio")
    .replace(/h2-continuation-xhigh/, "H2 · continuação Xhigh")
    .replace(/legal-tree-memory-persistent/, "Árvore legal · memória persistente")
    .replace(/-/g, " ");
}
export const runTitle = (run: Run) => !run.experiment || run.experiment === "Zugzwang run"
  ? `Execução ${shortId(run.id)}` : experimentLabel(run.experiment);
export function conditionLabel(run: Run): string {
  const search = run.task?.search as Record<string, unknown> | undefined;
  const hypothesis = search?.hypothesis_id;
  const backend = run.task?.backend_config as Record<string, unknown> | undefined;
  return [typeof hypothesis === "string" ? hypothesis.replace(/-/g, " ") : null,
    typeof backend?.reasoning_effort === "string" ? backend.reasoning_effort : null].filter(Boolean).join(" · ") || `ID ${shortId(run.id)}`;
}
export function runState(run: Run): { key: Exclude<StatusFilter, "all">; label: string; tone: Tone; detail: string } {
  const failedEpisode = run.episodes?.some(e => ["FAILED", "TERMINAL_FAILURE"].includes(e.status));
  if (run.status === "COMPLETED" && failedEpisode) return { key: "attention", label: "Revisar status", tone: "warn", detail: "O run consta como concluído, mas há episódio com falha. Consulte as evidências." };
  if (run.status === "RUNNING") return { key: "running", label: "Em execução", tone: "info", detail: "Status registrado no snapshot. Não confirma que o processo permanece ativo." };
  if (run.status === "COMPLETED") return { key: "completed", label: "Concluída", tone: "muted", detail: "Execução concluída. O resultado da partida é informado separadamente." };
  if (["CANCELED", "CANCELLED"].includes(run.status)) return { key: "attention", label: "Cancelada", tone: "muted", detail: "Execução cancelada; os lances registrados foram preservados." };
  if (["INTERRUPTED", "PAUSED"].includes(run.status)) return { key: "attention", label: "Interrompida", tone: "warn", detail: "Execução interrompida. O viewer não retoma nem altera runs." };
  return { key: "attention", label: run.status === "FAILED" ? "Falha de execução" : run.status || "Não informado", tone: "err", detail: "Verifique os eventos desta execução." };
}
export function resultLabel(ep?: Episode): string {
  if (!ep) return "Sem episódio";
  if (ep.result === "checkmate") return `${ep.winner === "White" ? "Brancas" : ep.winner === "Black" ? "Pretas" : "Lado não informado"} vencem · mate`;
  if (ep.result === "capped") return "Limite de lances · sem resultado";
  if (ep.result === "stalemate") return "Empate · afogamento";
  if (ep.result === "in_progress" || ep.status === "RUNNING") return "Partida em andamento";
  if (ep.result === "failed" || ep.status === "FAILED") return "Sem resultado · falha";
  if (["draw", "insufficient_material", "fivefold_repetition", "seventyfive_moves"].includes(ep.result)) return "Empate registrado";
  return "Sem desfecho informado";
}
export function activityAt(run: Run): number | null {
  const dates = [run.startedAt, run.finishedAt, ...((run.events ?? []).map(e => e.at)),
    ...((run.episodes ?? []).flatMap(e => (e.moves ?? []).map(m => m.committedAt)))];
  const times = dates.filter((d): d is string => Boolean(d)).map(Date.parse).filter(Number.isFinite);
  return times.length ? Math.max(...times) : null;
}
export function ageLabel(date: number | null, now = Date.now()): string {
  if (date === null) return "Horário não informado";
  const seconds = Math.max(0, Math.floor((now - date) / 1000));
  if (seconds < 60) return "agora";
  if (seconds < 3600) return `há ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `há ${Math.floor(seconds / 3600)} h`;
  return `há ${Math.floor(seconds / 86400)} d`;
}
export function routeFor(id: string, view: DetailView = "game", episode = 0, ply?: number) {
  const params = new URLSearchParams({ run: id, view, episode: String(episode) });
  if (ply !== undefined) params.set("ply", String(ply));
  return `#${params}`;
}
export function parseRoute(hash: string) {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  const view = p.get("view");
  const rawPly = p.get("ply");
  const integer = (n: string | null) => n !== null && /^\d+$/.test(n) ? Math.min(Number(n), 1_000_000) : 0;
  return { runId: p.get("run"), view: (["game", "analysis", "evidence"].includes(view ?? "") ? view : "game") as DetailView,
    episode: integer(p.get("episode")), ply: rawPly === null ? undefined : integer(rawPly) };
}
export function comparable(runs: Run[]): boolean {
  return runs.length > 1 && runs.every(r => Boolean(r.protocolHash) && r.protocolHash === runs[0]?.protocolHash);
}
