import { Link, useParams } from "@tanstack/react-router";
import { useMemo } from "react";
import { useRunGames, useRunSummary } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function RunDetailPage() {
  const params = useParams({ strict: false }) as { runId: string };
  const runId = params.runId;

  const summaryQuery = useRunSummary(runId);
  const gamesQuery = useRunGames(runId);

  const summary = summaryQuery.data;
  const games = gamesQuery.data ?? [];
  const report = summary?.report;
  const evaluated = asRecord(summary?.evaluated_report);
  const evaluatedMetrics = asRecord(evaluated.metrics);
  const evaluatedElo = asRecord(evaluated.elo_estimate);

  const metrics = useMemo(
    () => ({
      targetGames: asText(report?.num_games_target),
      validGames: asText(report?.num_games_valid),
      totalCost: asCost(report?.total_cost_usd),
      completionRate: asPercent(report?.completion_rate),
      acpl: asText(evaluatedMetrics.acpl_overall),
      elo: asText(evaluatedElo.elo_mle),
    }),
    [evaluatedElo.elo_mle, evaluatedMetrics.acpl_overall, report?.completion_rate, report?.num_games_target, report?.num_games_valid, report?.total_cost_usd],
  );

  return (
    <section>
      <PageHeader eyebrow="Run Detail" title={runId} subtitle="Overview of artifacts, reports and recorded games for this run." />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <MetricTile label="Target games" value={metrics.targetGames} />
        <MetricTile label="Valid games" value={metrics.validGames} />
        <MetricTile label="Total cost (USD)" value={metrics.totalCost} />
        <MetricTile label="Completion rate" value={metrics.completionRate} />
        <MetricTile label="ACPL" value={metrics.acpl} />
        <MetricTile label="Elo MLE" value={metrics.elo} />
      </div>

      {(summaryQuery.isLoading || gamesQuery.isLoading) && <p className="mb-3 text-sm text-[#506672]">Loading run artifacts...</p>}

      {(summaryQuery.isError || gamesQuery.isError) && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff0ed] px-3 py-2 text-sm text-[#8a3434]">
          Failed to load run detail.
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
      </div>
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

function asText(value: unknown): string {
  if (value === null || value === undefined) {
    return "--";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  return String(value);
}

function asCost(value: unknown): string {
  if (typeof value !== "number") {
    return "--";
  }
  return value.toFixed(4);
}

function asPercent(value: unknown): string {
  if (typeof value !== "number") {
    return "--";
  }
  return `${(value * 100).toFixed(1)}%`;
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
