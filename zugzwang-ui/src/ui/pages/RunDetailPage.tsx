import { Link, useParams } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useStartEvaluation, useRunGames, useRunSummary } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

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
  const games = gamesQuery.data ?? [];
  const runDir = summary?.run_meta.run_dir ?? "";
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
              disabled={startEval.isPending || !runDir}
              onClick={() => {
                setLastEvalJobId(null);
                const parsedElo = opponentElo.trim() ? Number(opponentElo) : null;
                startEval.mutate(
                  {
                    run_dir: runDir,
                    player_color: playerColor,
                    opponent_elo: parsedElo !== null && Number.isFinite(parsedElo) ? parsedElo : null,
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
