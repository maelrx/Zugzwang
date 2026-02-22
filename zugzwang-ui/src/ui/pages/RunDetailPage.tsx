import { useQueries } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { apiRequest } from "../../api/client";
import { useStartEvaluation, useRunGames, useRunSummary } from "../../api/queries";
import type { GameDetailResponse, GameListItem } from "../../api/types";
import { MoveQualityDistributionCard } from "../components/MoveQualityDistributionCard";
import { PhaseMetricCard } from "../components/PhaseMetricCard";
import { PageHeader } from "../components/PageHeader";
import { aggregateMoveQuality } from "../lib/moveQuality";
import { extractRunMetrics, formatCi, formatDecimal, formatInteger, formatRate, formatUsd } from "../lib/runMetrics";

const MAX_QUALITY_GAMES_SAMPLE = 20;
const EMPTY_GAMES: GameListItem[] = [];

export function RunDetailPage() {
  const params = useParams({ strict: false }) as { runId: string };
  const runId = params.runId;

  const summaryQuery = useRunSummary(runId);
  const gamesQuery = useRunGames(runId);
  const startEval = useStartEvaluation();
  const [playerColor, setPlayerColor] = useState<"white" | "black">("black");
  const [opponentElo, setOpponentElo] = useState("");
  const [lastEvalJobId, setLastEvalJobId] = useState<string | null>(null);

  const summary = summaryQuery.data;
  const games = gamesQuery.data ?? EMPTY_GAMES;
  const runDir = summary?.run_meta.run_dir ?? "";
  const report = asRecord(summary?.report);
  const evaluatedReport = asRecord(summary?.evaluated_report);
  const evaluationMeta = asRecord(evaluatedReport.evaluation);
  const stockfishMeta = asRecord(evaluationMeta.stockfish);

  const metrics = useMemo(() => extractRunMetrics(summary), [summary]);
  const hasEvaluatedReport = Boolean(summary?.run_meta.evaluated_report_exists && Object.keys(evaluatedReport).length > 0);
  const hasBudgetStop = metrics.stoppedDueToBudget === true;
  const sampledGames = useMemo(() => games.slice(0, MAX_QUALITY_GAMES_SAMPLE), [games]);

  const gameDetailQueries = useQueries({
    queries: sampledGames.map((game) => ({
      queryKey: ["run-detail-game-quality", runId, game.game_number] as const,
      queryFn: () => apiRequest<GameDetailResponse>(`/api/runs/${runId}/games/${game.game_number}`),
      enabled: runId.length > 0,
      staleTime: Infinity,
    })),
  });

  const sampledGameDetails = useMemo(
    () => gameDetailQueries.map((query) => query.data).filter((item): item is GameDetailResponse => Boolean(item)),
    [gameDetailQueries],
  );
  const qualityCounts = useMemo(() => aggregateMoveQuality(sampledGameDetails), [sampledGameDetails]);
  const qualityLoading = gameDetailQueries.some((query) => query.isLoading);
  const qualityError = gameDetailQueries.some((query) => query.isError);

  const opponentEloText = opponentElo.trim();
  const parsedOpponentElo = opponentEloText.length > 0 ? Number(opponentEloText) : null;
  const invalidOpponentElo = opponentEloText.length > 0 && !Number.isFinite(parsedOpponentElo);

  const metricCards = useMemo(
    () => [
      { label: "Target games", value: formatInteger(metrics.targetGames) },
      { label: "Valid games", value: formatInteger(metrics.validGames) },
      { label: "Completion rate", value: formatRate(metrics.completionRate) },
      { label: "Total cost (USD)", value: formatUsd(metrics.totalCostUsd) },
      { label: "ACPL", value: formatDecimal(metrics.acplOverall, 1) },
      { label: "Blunder rate", value: formatRate(metrics.blunderRate) },
      { label: "Best move agreement", value: formatRate(metrics.bestMoveAgreement) },
      { label: "Elo MLE", value: formatDecimal(metrics.eloMle, 1) },
      { label: "Elo CI 95%", value: formatCi(metrics.eloCiLower, metrics.eloCiUpper) },
      { label: "Avg tokens / move", value: formatDecimal(metrics.avgTokensPerMove, 1) },
      { label: "P95 latency ms", value: formatDecimal(metrics.p95MoveLatencyMs, 0) },
      { label: "Retrieval hit-rate", value: formatRate(metrics.retrievalHitRate) },
    ],
    [metrics],
  );

  return (
    <section>
      <PageHeader eyebrow="Run Detail" title={runId} subtitle="Overview of artifacts, reports and recorded games for this run." />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {metricCards.map((card) => (
          <MetricTile key={card.label} label={card.label} value={card.value} />
        ))}
      </div>

      {(summaryQuery.isLoading || gamesQuery.isLoading) && <p className="mb-3 text-sm text-[#506672]">Loading run artifacts...</p>}

      {(summaryQuery.isError || gamesQuery.isError) && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff0ed] px-3 py-2 text-sm text-[#8a3434]">
          Failed to load run detail.
        </p>
      )}

      {qualityError && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff0ed] px-3 py-2 text-sm text-[#8a3434]">
          Failed to load sampled games for move-quality distribution.
        </p>
      )}

      {hasBudgetStop && (
        <p className="mb-3 rounded-lg border border-[#d7b071] bg-[#fff3de] px-3 py-2 text-sm text-[#7d5618]">
          Run stopped due to budget guardrail.
          {metrics.budgetStopReason ? ` Reason: ${metrics.budgetStopReason}.` : ""}
        </p>
      )}

      <div className="mb-5 overflow-hidden rounded-2xl border border-[#d9d1c4] bg-white/85">
        <div className="grid grid-cols-[1fr_1fr_1fr] border-b border-[#e4ddd1] bg-[#f5f2ea] px-4 py-2 text-xs uppercase tracking-[0.14em] text-[#607684]">
          <span>Game</span>
          <span>Replay</span>
          <span>File path</span>
        </div>
        {games.length === 0 && !gamesQuery.isLoading && <p className="px-4 py-4 text-sm text-[#536874]">No games found.</p>}
        {games.map((game) => (
          <div
            key={game.game_number}
            className="grid grid-cols-[1fr_1fr_1fr] items-center border-b border-[#f0ece3] px-4 py-3 text-sm text-[#2b4351]"
          >
            <span>#{game.game_number}</span>
            <Link
              to="/runs/$runId/replay/$gameNumber"
              params={{ runId, gameNumber: String(game.game_number) }}
              className="w-fit rounded-md border border-[#1f637d] bg-[#1f637d] px-2.5 py-1 text-xs font-semibold text-[#edf8fd]"
            >
              Open replay
            </Link>
            <span className="truncate text-xs text-[#627987]">{game.path}</span>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-[#ddd5c8] bg-white/80 p-4">
          <h3 className="text-sm font-semibold text-[#264351]">Run evaluation</h3>
          <p className="mt-1 text-xs text-[#576d7a]">
            Launches `POST /api/jobs/evaluate` and returns a trackable job in the Jobs monitor.
          </p>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-[#4f6773]">
              Player color
              <select
                value={playerColor}
                onChange={(event) => setPlayerColor(event.target.value as "white" | "black")}
                className="mt-1 w-full rounded-md border border-[#d8d1c5] bg-[#f8f5ef] px-2 py-1.5 text-sm text-[#2b4552]"
              >
                <option value="white">white</option>
                <option value="black">black</option>
              </select>
            </label>

            <label className="text-xs text-[#4f6773]">
              Opponent Elo (optional)
              <input
                value={opponentElo}
                onChange={(event) => setOpponentElo(event.target.value)}
                placeholder="e.g. 1000"
                className="mt-1 w-full rounded-md border border-[#d8d1c5] bg-[#f8f5ef] px-2 py-1.5 text-sm text-[#2b4552]"
              />
            </label>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="rounded-md border border-[#1f637d] bg-[#1f637d] px-3 py-1.5 text-sm font-semibold text-[#edf8fd]"
              disabled={startEval.isPending || !runDir || invalidOpponentElo}
              onClick={() => {
                setLastEvalJobId(null);
                startEval.mutate(
                  {
                    run_dir: runDir,
                    player_color: playerColor,
                    opponent_elo: parsedOpponentElo !== null && Number.isFinite(parsedOpponentElo) ? parsedOpponentElo : null,
                    output_filename: "experiment_report_evaluated.json",
                  },
                  {
                    onSuccess: (job) => setLastEvalJobId(job.job_id),
                  },
                );
              }}
            >
              {startEval.isPending ? "Starting..." : "Start evaluation"}
            </button>

            <Link to="/jobs" className="rounded-md border border-[#d8d1c5] bg-white px-3 py-1.5 text-sm text-[#334c59]">
              Open jobs list
            </Link>
          </div>

          {invalidOpponentElo && (
            <p className="mt-2 rounded-md border border-[#cf8f8f] bg-[#fff1ef] px-2.5 py-1.5 text-xs text-[#8a3434]">
              Opponent Elo must be a valid number.
            </p>
          )}

          {startEval.isError && (
            <p className="mt-2 rounded-md border border-[#ce8d8d] bg-[#fff1ef] px-2.5 py-1.5 text-xs text-[#8a3434]">
              Failed to start evaluation job.
            </p>
          )}

          {lastEvalJobId && (
            <p className="mt-2 text-xs text-[#47606d]">
              Evaluation started:
              {" "}
              <Link to="/jobs/$jobId" params={{ jobId: lastEvalJobId }} className="font-semibold text-[#1f637d] underline">
                {lastEvalJobId}
              </Link>
            </p>
          )}

          <div className="mt-4 rounded-lg border border-[#ddd5c8] bg-[#f8f5ef] p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#5f7482]">
              Evaluation status: {hasEvaluatedReport ? "available" : "not generated yet"}
            </p>
            {hasEvaluatedReport ? (
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <MetricInline label="ACPL" value={formatDecimal(metrics.acplOverall, 1)} />
                <MetricInline label="Blunder rate" value={formatRate(metrics.blunderRate)} />
                <MetricInline label="Best move agreement" value={formatRate(metrics.bestMoveAgreement)} />
                <MetricInline label="Elo MLE" value={formatDecimal(metrics.eloMle, 1)} />
                <MetricInline label="Elo CI 95%" value={formatCi(metrics.eloCiLower, metrics.eloCiUpper)} />
                <MetricInline label="Provider" value={stringValue(evaluationMeta.provider) ?? "--"} />
                <MetricInline label="Player color" value={stringValue(evaluationMeta.player_color) ?? "--"} />
                <MetricInline label="SF depth" value={stringValue(stockfishMeta.depth) ?? "--"} />
              </div>
            ) : (
              <p className="mt-2 text-xs text-[#5f7482]">
                Run has no `experiment_report_evaluated.json` yet. Start evaluation to produce ACPL/blunder/Elo metrics.
              </p>
            )}
          </div>
        </section>

        <details className="rounded-2xl border border-[#ddd5c8] bg-white/80 p-4" open>
          <summary className="cursor-pointer text-sm font-semibold text-[#264351]">Resolved config</summary>
          <pre className="mt-3 max-h-[260px] overflow-auto rounded-lg bg-[#f8f5ef] p-3 font-['IBM_Plex_Mono'] text-xs text-[#334b58]">
            {toPrettyJson(summary?.resolved_config)}
          </pre>
        </details>

        <details className="rounded-2xl border border-[#ddd5c8] bg-white/80 p-4" open>
          <summary className="cursor-pointer text-sm font-semibold text-[#264351]">Experiment report</summary>
          <pre className="mt-3 max-h-[260px] overflow-auto rounded-lg bg-[#f8f5ef] p-3 font-['IBM_Plex_Mono'] text-xs text-[#334b58]">
            {toPrettyJson(report)}
          </pre>
        </details>

        <details className="rounded-2xl border border-[#ddd5c8] bg-white/80 p-4" open={hasEvaluatedReport}>
          <summary className="cursor-pointer text-sm font-semibold text-[#264351]">Evaluated report</summary>
          <pre className="mt-3 max-h-[260px] overflow-auto rounded-lg bg-[#f8f5ef] p-3 font-['IBM_Plex_Mono'] text-xs text-[#334b58]">
            {toPrettyJson(evaluatedReport)}
          </pre>
        </details>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <PhaseMetricCard
          title="ACPL by phase"
          description="Lower is better. Useful to spot opening/middlegame/endgame weaknesses."
          values={metrics.acplByPhase}
          format="decimal"
        />
        <PhaseMetricCard
          title="Retrieval hit-rate by phase"
          description="Higher is better. Indicates whether RAG is actually being hit per phase."
          values={metrics.retrievalHitRateByPhase}
          format="percent"
        />
        <MoveQualityDistributionCard
          title="Move-quality distribution"
          subtitle={`Computed from sampled game moves (up to ${MAX_QUALITY_GAMES_SAMPLE} games).`}
          counts={qualityCounts}
        />
      </div>

      {qualityLoading && (
        <p className="mt-3 rounded-lg border border-[#cfd7dc] bg-[#f3f7fa] px-3 py-2 text-sm text-[#48616f]">
          Loading sampled games for move-quality distribution...
        </p>
      )}
    </section>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-xl border border-[#d9d2c6] bg-white/85 px-3 py-2">
      <p className="text-xs uppercase tracking-[0.14em] text-[#647987]">{label}</p>
      <p className="mt-1 text-base font-semibold text-[#1e3948]">{value}</p>
    </article>
  );
}

function MetricInline({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[#ddd5c8] bg-white px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[#647987]">{label}</p>
      <p className="mt-1 text-xs font-semibold text-[#24414f]">{value}</p>
    </div>
  );
}

function toPrettyJson(value: unknown): string {
  if (value === null || value === undefined) {
    return "{}";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  return {};
}

function stringValue(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}
