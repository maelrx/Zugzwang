import { useQueries } from "@tanstack/react-query";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { Activity, ChevronDown, ChevronRight, Compass, FlaskConical, Home, Menu, Play, Settings, SplitSquareHorizontal, TableProperties } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { apiRequest } from "../../api/client";
import { useJobs } from "../../api/queries";
import type { JobResponse, RunProgressResponse } from "../../api/types";
import { useSidebarStore } from "../../stores/sidebarStore";
import { ToastContainer } from "../components/ToastContainer";
import { useJobWatcher } from "../hooks/useJobWatcher";

type NavItem = {
  label: string;
  to: string;
  icon: ComponentType<{ className?: string }>;
  badgeSource?: "active-jobs";
};

const NAV_ITEMS: NavItem[] = [
  { label: "Command Center", to: "/dashboard", icon: Home, badgeSource: "active-jobs" },
  { label: "Quick Play", to: "/quick-play", icon: Play },
  { label: "Experiment Lab", to: "/lab", icon: FlaskConical },
  { label: "Runs", to: "/runs", icon: TableProperties },
  { label: "Compare", to: "/compare", icon: SplitSquareHorizontal },
  { label: "Settings", to: "/settings", icon: Settings },
];

const BADGE_PULSE_MS = 900;

export function AppShell() {
  useJobWatcher();

  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const jobsQuery = useJobs();
  const jobs = jobsQuery.data ?? [];
  const activeJobs = useMemo(() => jobs.filter(isActiveJob), [jobs]);
  const activeJobsCount = activeJobs.length;

  const collapsed = useSidebarStore((state) => state.collapsed);
  const toggleCollapsed = useSidebarStore((state) => state.toggleCollapsed);
  const activeSection = useSidebarStore((state) => state.activeSection);
  const setActiveSection = useSidebarStore((state) => state.setActiveSection);

  const [pulseBadge, setPulseBadge] = useState(false);
  const previousActiveCountRef = useRef(activeJobsCount);

  useEffect(() => {
    const previous = previousActiveCountRef.current;
    previousActiveCountRef.current = activeJobsCount;
    if (activeJobsCount <= previous || activeJobsCount <= 0) {
      return;
    }
    setPulseBadge(true);
    const timer = window.setTimeout(() => setPulseBadge(false), BADGE_PULSE_MS);
    return () => window.clearTimeout(timer);
  }, [activeJobsCount]);

  useEffect(() => {
    if (activeJobsCount === 0 && activeSection === "active-jobs") {
      setActiveSection("navigation");
    }
  }, [activeJobsCount, activeSection, setActiveSection]);

  const progressQueries = useQueries({
    queries: activeJobs.map((job) => ({
      queryKey: ["sidebar-job-progress", job.job_id] as const,
      queryFn: () => apiRequest<RunProgressResponse>(`/api/jobs/${job.job_id}/progress`),
      staleTime: 0,
      refetchInterval: 2_000,
      retry: 1,
    })),
  });

  const progressByJobId = useMemo(() => {
    const map = new Map<string, RunProgressResponse>();
    for (let index = 0; index < activeJobs.length; index += 1) {
      const data = progressQueries[index]?.data;
      if (data) {
        map.set(activeJobs[index].job_id, data);
      }
    }
    return map;
  }, [activeJobs, progressQueries]);

  const shellColumns = collapsed ? "md:grid-cols-[88px_1fr]" : "md:grid-cols-[300px_1fr]";
  const jobsPanelOpen = !collapsed && activeSection === "active-jobs" && activeJobsCount > 0;

  return (
    <div className="min-h-screen bg-[var(--color-surface-canvas)] text-[var(--color-text-primary)]">
      <div className={["mx-auto grid min-h-screen w-full max-w-[1440px] grid-cols-1", shellColumns].join(" ")}>
        <aside className="border-b border-[var(--color-border-default)] bg-[var(--color-surface-sidebar)] p-5 backdrop-blur md:border-b-0 md:border-r">
          <div className="mb-7">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border-subtle)] bg-[var(--color-surface-raised)] px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-text-secondary)]">
                <Compass className="h-3.5 w-3.5" />
                {!collapsed ? "Frontend Track" : "V2"}
              </p>
              <button
                type="button"
                className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-1.5 text-[var(--color-text-secondary)]"
                onClick={toggleCollapsed}
                aria-label="Toggle sidebar"
              >
                <Menu className="h-4 w-4" />
              </button>
            </div>

            {!collapsed ? (
              <>
                <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">Zugzwang UI</h1>
                <p className="mt-1 text-sm text-[var(--color-text-secondary)]">FastAPI + React workspace for experiments and analysis.</p>
              </>
            ) : null}

            <p className="sr-only">
              <Compass className="h-3.5 w-3.5" />
              Frontend Track
            </p>
          </div>

          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => {
              const active = isActiveRoute(pathname, item.to);
              const Icon = item.icon;
              const showActiveJobsBadge = item.badgeSource === "active-jobs" && activeJobsCount > 0;
              const badgePulseClass = pulseBadge ? "animate-pulse" : "";
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={[
                    "flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors",
                    active
                      ? "border-[var(--color-primary-700)] bg-[var(--color-primary-700)] text-[var(--color-surface-canvas)]"
                      : "border-[var(--color-border-default)] bg-[var(--color-surface-raised)] text-[var(--color-text-primary)] hover:border-[var(--color-border-strong)]",
                  ].join(" ")}
                >
                  <Icon className="h-4 w-4" />
                  {!collapsed ? <span>{item.label}</span> : null}
                  {showActiveJobsBadge ? (
                    <span
                      className={[
                        collapsed ? "ml-0" : "ml-auto",
                        "rounded-full border border-current/30 px-2 py-0.5 text-[11px] font-semibold",
                        badgePulseClass,
                      ].join(" ")}
                    >
                      {activeJobsCount}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </nav>

          {!collapsed ? (
            <section className="mt-4 rounded-xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-3">
              <button
                type="button"
                onClick={() => setActiveSection(jobsPanelOpen ? "navigation" : "active-jobs")}
                className="flex w-full items-center justify-between gap-2 text-left"
                aria-expanded={jobsPanelOpen}
                aria-controls="active-jobs-panel"
              >
                <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
                  <Activity className="h-3.5 w-3.5" />
                  Active Jobs
                </span>
                <span className="inline-flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
                  <span className="rounded-full border border-[var(--color-border-default)] px-2 py-0.5 font-semibold text-[var(--color-text-primary)]">
                    {activeJobsCount}
                  </span>
                  {jobsPanelOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </span>
              </button>

              {activeJobsCount === 0 ? (
                <p className="mt-2 text-xs text-[var(--color-text-secondary)]">No active jobs. Launch from Quick Play or Experiment Lab.</p>
              ) : null}

              {jobsPanelOpen ? (
                <div id="active-jobs-panel" className="mt-3 space-y-2">
                  {activeJobs.map((job) => {
                    const progress = progressByJobId.get(job.job_id);
                    const gamesWritten = progress?.games_written ?? 0;
                    const gamesTarget = progress?.games_target ?? 0;
                    const completion = gamesTarget > 0 ? Math.max(0, Math.min(100, (gamesWritten / gamesTarget) * 100)) : 0;
                    const runLabel = (job.run_id ?? job.job_id).slice(0, 26);
                    return (
                      <Link
                        key={job.job_id}
                        to="/dashboard/jobs/$jobId"
                        params={{ jobId: job.job_id }}
                        className="block rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-2.5 py-2 hover:border-[var(--color-border-strong)]"
                      >
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <p className="truncate text-xs font-semibold text-[var(--color-text-primary)]">{runLabel}</p>
                          <span className="rounded-full border border-[var(--color-border-default)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-secondary)]">
                            {formatJobStatusLabel(job)}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-[var(--color-border-subtle)]">
                          <div
                            className="h-full rounded-full bg-[var(--color-primary-700)] transition-all"
                            style={{ width: `${completion}%` }}
                          />
                        </div>
                        <p className="mt-1 text-[10px] text-[var(--color-text-secondary)]">
                          {gamesTarget > 0 ? `${gamesWritten}/${gamesTarget} games` : `${gamesWritten} games`}
                        </p>
                      </Link>
                    );
                  })}
                </div>
              ) : null}
            </section>
          ) : null}

          {!collapsed ? (
            <div className="mt-4 rounded-xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-3 text-xs text-[var(--color-text-secondary)]">
              <p className="font-semibold text-[var(--color-text-primary)]">Current milestone</p>
              <p className="mt-1">M9: cutover + legacy cleanup</p>
            </div>
          ) : null}
        </aside>

        <main className="p-5 md:p-8">
          <Outlet />
        </main>
      </div>
      <ToastContainer />
    </div>
  );
}

function isActiveRoute(pathname: string, to: string): boolean {
  if (to === "/dashboard") {
    return pathname === "/" || pathname === "/dashboard" || pathname.startsWith("/dashboard/");
  }
  if (to === "/compare") {
    return pathname === "/compare" || pathname === "/runs/compare";
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}

function isActiveJob(job: JobResponse): boolean {
  return job.status === "running" || job.status === "queued";
}

function formatJobStatusLabel(job: JobResponse): string {
  if (job.job_type === "evaluate" && job.status === "running") {
    return "evaluating";
  }
  return job.status;
}
