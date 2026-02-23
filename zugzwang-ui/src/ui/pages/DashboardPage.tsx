import { useQueries } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useMemo } from "react";
import { apiRequest } from "../../api/client";
import { useDashboardKpis, useJobs, useRuns } from "../../api/queries";
import type { JobResponse, RunListItem, RunProgressResponse } from "../../api/types";
import { useCompareStore } from "../../stores/compareStore";
import { ProgressBar } from "../components/ProgressBar";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { PageHeader } from "../components/PageHeader";
import { formatDecimal, formatUsd } from "../lib/runMetrics";

const RECENT_RUN_ROWS = 8;
const EMPTY_JOBS: JobResponse[] = [];
const EMPTY_RUNS: RunListItem[] = [];

export function DashboardPage() {
  const kpisQuery = useDashboardKpis(80);
  const jobsQuery = useJobs();
  const runsQuery = useRuns({ sortBy: "created_at_utc", sortDir: "desc", limit: RECENT_RUN_ROWS });

  const jobs = jobsQuery.data ?? EMPTY_JOBS;
  const runs = runsQuery.data ?? EMPTY_RUNS;
  const activeJobs = useMemo(() => jobs.filter((job) => job.status === "running" || job.status === "queued"), [jobs]);

  const selectedRunIds = useCompareStore((state) => state.selectedRunIds);
  const toggleRunSelection = useCompareStore((state) => state.toggleRunSelection);
  const clearSelection = useCompareStore((state) => state.clearSelection);

  const progressQueries = useQueries({
    queries: activeJobs.map((job) => ({
      queryKey: ["job-progress", job.job_id] as const,
      queryFn: () => apiRequest<RunProgressResponse>(`/api/jobs/${job.job_id}/progress`),
      staleTime: 0,
      refetchInterval: 2_000,
    })),
  });

  const progressByJobId = useMemo(() => {
    const entries = new Map<string, RunProgressResponse>();
    for (let index = 0; index < activeJobs.length; index += 1) {
      const data = progressQueries[index]?.data;
      if (data) {
        entries.set(activeJobs[index].job_id, data);
      }
    }
    return entries;
  }, [activeJobs, progressQueries]);

  const kpis = kpisQuery.data;
  const selectedCount = selectedRunIds.length;
  const canCompare = selectedCount >= 2;
  const hasErrors = kpisQuery.isError || jobsQuery.isError || runsQuery.isError || progressQueries.some((query) => query.isError);

  return (
    <section>
      <PageHeader
        eyebrow="Home"
        title="Command Center"
        subtitle="Research operations snapshot with active jobs, quick actions, and compare-ready recent runs."
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Total runs" value={String(kpis?.total_runs ?? 0)} hint="Indexed from /api/dashboard/kpis" />
        <StatCard label="Best Elo" value={formatDecimal(kpis?.best_elo, 1)} hint="Highest evaluated run Elo" />
        <StatCard label="Avg ACPL" value={formatDecimal(kpis?.avg_acpl, 1)} hint="Across evaluated runs" />
        <StatCard label="Total cost" value={formatUsd(kpis?.total_cost_usd, 4)} hint="All-time aggregate spend" />
        <StatCard label="Active jobs" value={String(activeJobs.length)} hint="Polled from /api/jobs" />
      </div>

      <section className="mt-5 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Quick actions</p>
          {kpis?.last_run_id ? (
            <span className="text-xs text-[var(--color-text-secondary)]">Last run: {kpis.last_run_id}</span>
          ) : (
            <span className="text-xs text-[var(--color-text-secondary)]">No runs yet</span>
          )}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            to="/quick-play"
            className="inline-flex items-center rounded-lg border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-2 text-sm font-semibold text-[var(--color-surface-canvas)]"
          >
            Quick Play
          </Link>
          <Link
            to="/lab"
            className="inline-flex items-center rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm font-semibold text-[var(--color-text-primary)]"
          >
            New Experiment
          </Link>
          {kpis?.last_run_id ? (
            <Link
              to="/runs/$runId"
              params={{ runId: kpis.last_run_id }}
              className="inline-flex items-center rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm font-semibold text-[var(--color-text-primary)]"
            >
              View Last Run
            </Link>
          ) : null}
        </div>

        <div className="mt-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Research flow</p>
          <div className="mt-2 grid gap-1.5 text-xs text-[var(--color-text-secondary)]">
            <span>1. Launch experiment from Experiment Lab or Quick Play.</span>
            <span>2. Follow active jobs in this command center or Jobs page.</span>
            <span>3. Open Run Detail for metadata and quality, then Compare for statistical report.</span>
          </div>
        </div>
      </section>

      <section className="mt-5 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <div className="mb-3 flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Active jobs</p>
          {activeJobs.length > 0 ? <StatusBadge label={`${activeJobs.length} running`} tone="info" /> : null}
        </div>

        {activeJobs.length === 0 ? (
          <div className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-sunken)] px-3 py-3 text-sm text-[var(--color-text-secondary)]">
            No active jobs. Launch one from Quick Play or the Experiment Lab.
          </div>
        ) : (
          <div className="grid gap-3">
            {activeJobs.map((job) => {
              const progress = progressByJobId.get(job.job_id);
              const gamesWritten = progress?.games_written ?? 0;
              const gamesTarget = progress?.games_target ?? 0;
              const progressLabel = gamesTarget > 0 ? `${gamesWritten}/${gamesTarget} games` : `${gamesWritten} games`;

              return (
                <article
                  key={job.job_id}
                  className="rounded-xl border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-3 py-3"
                >
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold text-[var(--color-text-primary)]">{job.run_id ?? job.job_id}</p>
                    <StatusBadge label={job.status} tone="info" />
                  </div>
                  <ProgressBar value={gamesWritten} max={Math.max(1, gamesTarget || gamesWritten)} label={progressLabel} />
                  <div className="mt-2">
                    <Link
                      to="/dashboard/jobs/$jobId"
                      params={{ jobId: job.job_id }}
                      className="text-xs font-semibold text-[var(--color-primary-700)] hover:underline"
                    >
                      Open job details
                    </Link>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="mt-5 overflow-x-auto rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border-subtle)] px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Recent runs</p>
          <div className="flex items-center gap-2">
            {canCompare ? (
              <Link
                to="/compare"
                className="inline-flex items-center rounded-lg border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-2.5 py-1.5 text-xs font-semibold text-[var(--color-surface-canvas)]"
              >
                Compare selected ({selectedCount})
              </Link>
            ) : null}
            {selectedCount > 0 ? (
              <button
                type="button"
                onClick={clearSelection}
                className="inline-flex items-center rounded-lg border border-[var(--color-border-strong)] px-2.5 py-1.5 text-xs font-semibold text-[var(--color-text-primary)]"
              >
                Clear selection
              </button>
            ) : null}
          </div>
        </div>

        <div className="grid min-w-[920px] grid-cols-[0.35fr_2.1fr_1.3fr_1fr_1fr_1fr_1fr] border-b border-[var(--color-border-subtle)] bg-[var(--color-surface-sunken)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
          <span />
          <span>Run ID</span>
          <span>Model + Metadata</span>
          <span>Games</span>
          <span>Elo</span>
          <span>Cost</span>
          <span>Status</span>
        </div>

        {!runsQuery.isLoading && runs.length === 0 ? (
          <p className="px-4 py-4 text-sm text-[var(--color-text-secondary)]">No runs found yet. Start by playing one game or launching an experiment.</p>
        ) : null}

        {runs.map((run) => (
          <div
            key={run.run_id}
            className="grid min-w-[920px] grid-cols-[0.35fr_2.1fr_1.3fr_1fr_1fr_1fr_1fr] items-center border-b border-[var(--color-border-subtle)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
          >
            <input
              type="checkbox"
              checked={selectedRunIds.includes(run.run_id)}
              onChange={() => toggleRunSelection(run.run_id)}
              aria-label={`Select ${run.run_id} for compare`}
              className="h-4 w-4 rounded border-[var(--color-border-strong)]"
            />
            <Link to="/runs/$runId" params={{ runId: run.run_id }} className="truncate font-medium text-[var(--color-primary-700)] hover:underline">
              {run.run_id}
            </Link>
            <div className="min-w-0">
              <p className="truncate text-xs text-[var(--color-text-secondary)]">{run.inferred_model_label ?? "--"}</p>
              <p className="truncate text-[11px] text-[var(--color-text-muted)]">tpl: {formatTemplateShort(run.inferred_config_template)}</p>
              <p className="truncate text-[11px] text-[var(--color-text-muted)]">cfg: {formatHashShort(run.config_hash)}</p>
            </div>
            <span className="text-xs text-[var(--color-text-secondary)]">{formatGames(run.num_games_valid, run.num_games_target)}</span>
            <span className="text-xs text-[var(--color-text-secondary)]">{formatDecimal(run.elo_estimate, 1)}</span>
            <span className="text-xs text-[var(--color-text-secondary)]">{formatUsd(run.total_cost_usd, 4)}</span>
            <StatusBadge label={formatEvalStatus(run.inferred_eval_status)} tone={evalStatusTone(run.inferred_eval_status)} />
          </div>
        ))}
      </section>

      {hasErrors ? (
        <div className="mt-5 rounded-xl border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-4 py-3 text-sm text-[var(--color-error-text)]">
          Failed to load one or more command center widgets from API.
        </div>
      ) : null}
    </section>
  );
}

function formatGames(valid: number | null | undefined, target: number | null | undefined): string {
  if (typeof valid !== "number" || typeof target !== "number") {
    return "--";
  }
  return `${valid}/${target}`;
}

function formatEvalStatus(status: RunListItem["inferred_eval_status"]): string {
  if (status === "evaluated") {
    return "evaluated";
  }
  if (status === "needs_eval") {
    return "needs eval";
  }
  if (status === "pending_report") {
    return "pending";
  }
  return "unknown";
}

function evalStatusTone(status: RunListItem["inferred_eval_status"]): "neutral" | "success" | "warning" {
  if (status === "evaluated") {
    return "success";
  }
  if (status === "needs_eval") {
    return "warning";
  }
  return "neutral";
}

function formatTemplateShort(value: string | null | undefined): string {
  if (!value || value.trim().length === 0) {
    return "--";
  }
  const normalized = value.replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] ?? normalized;
}

function formatHashShort(value: string | null | undefined): string {
  if (!value || value.trim().length === 0) {
    return "--";
  }
  if (value.length <= 12) {
    return value;
  }
  return `${value.slice(0, 8)}...`;
}
