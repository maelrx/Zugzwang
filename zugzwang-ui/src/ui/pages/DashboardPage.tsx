import { useQueries } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useMemo } from "react";
import { apiRequest } from "../../api/client";
import { useJobs, useRuns } from "../../api/queries";
import type { JobResponse, RunListItem, RunSummaryResponse } from "../../api/types";
import { InfoCard } from "../components/InfoCard";
import { PageHeader } from "../components/PageHeader";
import { computeDashboardKpis, extractRunMetrics, formatDecimal, formatRate, formatUsd } from "../lib/runMetrics";

const DASHBOARD_SUMMARY_LIMIT = 20;
const RECENT_RUN_ROWS = 8;
const EMPTY_JOBS: JobResponse[] = [];
const EMPTY_RUNS: RunListItem[] = [];

export function DashboardPage() {
  const jobsQuery = useJobs();
  const runsQuery = useRuns();

  const jobs = jobsQuery.data ?? EMPTY_JOBS;
  const runs = runsQuery.data ?? EMPTY_RUNS;
  const sampledRuns = runs.slice(0, DASHBOARD_SUMMARY_LIMIT);

  const summaryQueries = useQueries({
    queries: sampledRuns.map((run) => ({
      queryKey: ["run-summary-dashboard", run.run_id] as const,
      queryFn: () => apiRequest<RunSummaryResponse>(`/api/runs/${run.run_id}`),
      staleTime: 30_000,
    })),
  });

  const summaries = useMemo(
    () => summaryQueries.map((query) => query.data).filter((summary): summary is RunSummaryResponse => Boolean(summary)),
    [summaryQueries],
  );

  const summaryByRunId = useMemo(() => {
    const map = new Map<string, RunSummaryResponse>();
    for (const summary of summaries) {
      map.set(summary.run_meta.run_id, summary);
    }
    return map;
  }, [summaries]);

  const recentRows = useMemo(
    () =>
      runs.slice(0, RECENT_RUN_ROWS).map((run) => {
        const summary = summaryByRunId.get(run.run_id);
        const metrics = extractRunMetrics(summary);
        return {
          runId: run.run_id,
          completionRate: formatRate(metrics.completionRate),
          costUsd: formatUsd(metrics.totalCostUsd),
          acpl: formatDecimal(metrics.acplOverall, 1),
          evaluated: run.evaluated_report_exists ? "yes" : "no",
        };
      }),
    [runs, summaryByRunId],
  );

  const kpis = useMemo(() => computeDashboardKpis(jobs, runs, summaries), [jobs, runs, summaries]);

  const summariesLoading = summaryQueries.some((query) => query.isLoading);
  const summariesError = summaryQueries.some((query) => query.isError);

  return (
    <section>
      <PageHeader
        eyebrow="Home"
        title="Research Operations Dashboard"
        subtitle="Operational KPIs and recent experiment outcomes, all loaded from FastAPI routes."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <InfoCard title="Active jobs" value={String(kpis.activeJobs)} hint={jobsQuery.isLoading ? "Loading jobs..." : "Polled from /api/jobs"} />
        <InfoCard title="Runs indexed" value={String(kpis.runsIndexed)} hint={runsQuery.isLoading ? "Loading runs..." : "Loaded from /api/runs"} />
        <InfoCard
          title="Completion rate"
          value={formatRate(kpis.completionRate)}
          hint={summariesLoading ? "Computing from latest reports..." : "Aggregate valid/target games."}
        />
        <InfoCard title="Total spend (USD)" value={formatUsd(kpis.totalSpendUsd)} hint="Sum of report.total_cost_usd across sampled runs." />
        <InfoCard title="Avg ACPL" value={formatDecimal(kpis.avgAcpl, 1)} hint="Average ACPL from sampled evaluated reports." />
        <InfoCard title="Evaluated runs" value={String(kpis.evaluatedRuns)} hint={`Budget-stopped runs: ${kpis.budgetStops}`} />
      </div>

      <div className="mt-5 overflow-x-auto rounded-2xl border border-[#d9d1c4] bg-white/85 shadow-[0_10px_24px_rgba(16,32,41,0.08)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#e2ddd2] bg-[#f5f2ea] px-4 py-2">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#5e7382]">Recent runs</p>
          <span className="text-xs text-[#5e7382]">Last run: {kpis.lastRunId ?? "--"}</span>
        </div>

        <div className="grid min-w-[720px] grid-cols-[2fr_1fr_1fr_1fr_1fr] border-b border-[#ece6da] px-4 py-2 text-xs uppercase tracking-[0.12em] text-[#627786]">
          <span>Run ID</span>
          <span>Completion</span>
          <span>Cost USD</span>
          <span>ACPL</span>
          <span>Evaluated</span>
        </div>

        {recentRows.length === 0 && !runsQuery.isLoading && <p className="px-4 py-4 text-sm text-[#5d6f7a]">No runs found.</p>}

        {recentRows.map((row) => (
          <div key={row.runId} className="grid min-w-[720px] grid-cols-[2fr_1fr_1fr_1fr_1fr] items-center border-b border-[#f0ece2] px-4 py-3 text-sm text-[#27404f]">
            <Link to="/runs/$runId" params={{ runId: row.runId }} className="truncate font-medium text-[#1d5d77] hover:underline">
              {row.runId}
            </Link>
            <span>{row.completionRate}</span>
            <span>{row.costUsd}</span>
            <span>{row.acpl}</span>
            <span>{row.evaluated}</span>
          </div>
        ))}
      </div>

      {(jobsQuery.isError || runsQuery.isError || summariesError) && (
        <div className="mt-5 rounded-xl border border-[#c58f8f] bg-[#fff3f1] px-4 py-3 text-sm text-[#7f2d2d]">
          Failed to load one or more dashboard widgets from API.
        </div>
      )}
    </section>
  );
}
