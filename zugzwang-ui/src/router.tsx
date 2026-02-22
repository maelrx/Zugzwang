import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { AppShell } from "./ui/layout/AppShell";
import { DashboardPage } from "./ui/pages/DashboardPage";
import { JobDetailPage } from "./ui/pages/JobDetailPage";
import { JobsPage } from "./ui/pages/JobsPage";
import { ReplayPage } from "./ui/pages/ReplayPage";
import { RunComparePage } from "./ui/pages/RunComparePage";
import { RunLabPage } from "./ui/pages/RunLabPage";
import { RunDetailPage } from "./ui/pages/RunDetailPage";
import { RunsPage } from "./ui/pages/RunsPage";
import { SettingsPage } from "./ui/pages/SettingsPage";

const rootRoute = createRootRoute({
  component: AppShell,
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: DashboardPage,
});

const runLabRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/run-lab",
  component: RunLabPage,
});

const jobsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs",
  component: JobsPage,
});

const jobDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs/$jobId",
  component: JobDetailPage,
});

const runsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/runs",
  component: RunsPage,
});

const runCompareRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/runs/compare",
  component: RunComparePage,
});

const runDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/runs/$runId",
  component: RunDetailPage,
});

const replayRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/runs/$runId/replay/$gameNumber",
  component: ReplayPage,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsPage,
});

const routeTree = rootRoute.addChildren([
  dashboardRoute,
  runLabRoute,
  jobsRoute,
  jobDetailRoute,
  runsRoute,
  runCompareRoute,
  runDetailRoute,
  replayRoute,
  settingsRoute,
]);

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  defaultPendingComponent: () => <p className="p-6 text-sm text-slate-600">Loading page...</p>,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
