import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { Compass, FlaskConical, Home, Menu, Play, Settings, SplitSquareHorizontal, TableProperties } from "lucide-react";
import { type ComponentType } from "react";
import { useJobs } from "../../api/queries";
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

export function AppShell() {
  useJobWatcher();

  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const jobsQuery = useJobs();
  const activeJobsCount = (jobsQuery.data ?? []).filter((job) => job.status === "running" || job.status === "queued").length;

  const collapsed = useSidebarStore((state) => state.collapsed);
  const toggleCollapsed = useSidebarStore((state) => state.toggleCollapsed);

  const shellColumns = collapsed ? "md:grid-cols-[88px_1fr]" : "md:grid-cols-[280px_1fr]";

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
              const showActiveJobsBadge = item.badgeSource === "active-jobs" && activeJobsCount > 0 && !collapsed;
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
                    <span className="ml-auto rounded-full border border-current/30 px-2 py-0.5 text-[11px] font-semibold">{activeJobsCount}</span>
                  ) : null}
                </Link>
              );
            })}
          </nav>

          {!collapsed ? (
            <div className="mt-7 rounded-xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-3 text-xs text-[var(--color-text-secondary)]">
              <p className="font-semibold text-[var(--color-text-primary)]">Current milestone</p>
              <p className="mt-1">M3: command center delivery</p>
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
    return pathname === "/" || pathname === "/dashboard";
  }
  if (to === "/compare") {
    return pathname === "/compare" || pathname === "/runs/compare";
  }
  return pathname === to || pathname.startsWith(`${to}/`);
}
