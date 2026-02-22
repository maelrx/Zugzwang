import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { AppShell } from "./ui/layout/AppShell";
import { DashboardPage } from "./ui/pages/DashboardPage";
import { JobsPage } from "./ui/pages/JobsPage";
import { RunLabPage } from "./ui/pages/RunLabPage";
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

const runsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/runs",
  component: RunsPage,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsPage,
});

const routeTree = rootRoute.addChildren([dashboardRoute, runLabRoute, jobsRoute, runsRoute, settingsRoute]);

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

