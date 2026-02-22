import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { router } from "../../router";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly url: string;
  private listeners = new Map<string, Array<(event: { data: string }) => void>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: { data: string }) => void) {
    const current = this.listeners.get(type) ?? [];
    current.push(listener);
    this.listeners.set(type, current);
  }

  close() {
    // no-op for tests
  }

  emit(type: string, data: string) {
    const listeners = this.listeners.get(type) ?? [];
    for (const listener of listeners) {
      listener({ data });
    }
  }
}

describe("run lab launch flow", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = toUrl(input);
      const pathname = url.pathname;
      const method = (init?.method ?? "GET").toUpperCase();

      if (pathname === "/api/configs" && method === "GET") {
        return jsonResponse({
          baselines: [{ name: "best_known_start", path: "configs/baselines/best_known_start.yaml", category: "baselines" }],
          ablations: [],
        });
      }

      if (pathname === "/api/jobs/run" && method === "POST") {
        return jsonResponse({
          job_id: "job-run-1",
          job_type: "run",
          status: "running",
          pid: 111,
          command: ["python", "-m", "zugzwang.cli", "run"],
          created_at_utc: "2026-02-22T00:00:00Z",
          updated_at_utc: null,
          stdout_path: "results/ui_jobs/logs/job-run-1.stdout.log",
          stderr_path: "results/ui_jobs/logs/job-run-1.stderr.log",
          run_id: "run-1",
          run_dir: "results/runs/run-1",
          meta: {},
          result_payload: null,
          exit_code: null,
        });
      }

      if (pathname === "/api/jobs/play" && method === "POST") {
        return jsonResponse({
          job_id: "job-play-1",
          job_type: "play",
          status: "running",
          pid: 222,
          command: ["python", "-m", "zugzwang.cli", "play"],
          created_at_utc: "2026-02-22T00:00:00Z",
          updated_at_utc: null,
          stdout_path: "results/ui_jobs/logs/job-play-1.stdout.log",
          stderr_path: "results/ui_jobs/logs/job-play-1.stderr.log",
          run_id: "run-play-1",
          run_dir: "results/runs/run-play-1",
          meta: {},
          result_payload: null,
          exit_code: null,
        });
      }

      if (pathname === "/api/jobs/job-play-1" && method === "GET") {
        return jsonResponse({
          job_id: "job-play-1",
          job_type: "play",
          status: "completed",
          pid: 222,
          command: ["python", "-m", "zugzwang.cli", "play"],
          created_at_utc: "2026-02-22T00:00:00Z",
          updated_at_utc: "2026-02-22T00:00:03Z",
          stdout_path: "results/ui_jobs/logs/job-play-1.stdout.log",
          stderr_path: "results/ui_jobs/logs/job-play-1.stderr.log",
          run_id: "run-play-1",
          run_dir: "results/runs/run-play-1",
          meta: {},
          result_payload: null,
          exit_code: 0,
        });
      }

      if (pathname === "/api/jobs/job-play-1/progress" && method === "GET") {
        return jsonResponse({
          run_id: "run-play-1",
          status: "completed",
          games_written: 1,
          games_target: 1,
          run_dir: "results/runs/run-play-1",
          stopped_due_to_budget: false,
          budget_stop_reason: null,
          latest_report: null,
          log_tail: "",
        });
      }

      return jsonResponse({ detail: `Unhandled mock route: ${method} ${pathname}` }, 404);
    });
  });

  afterEach(async () => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    await router.navigate({ to: "/" });
  });

  it("starts play from run lab and navigates to job detail", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
        },
      },
    });

    await router.navigate({ to: "/run-lab" });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await screen.findByRole("heading", { name: "Experiment Launch Workbench" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Play (1 game)" }));

    await screen.findByRole("heading", { name: "Job job-play-1" });

    await waitFor(() => {
      const calls = vi.mocked(globalThis.fetch).mock.calls;
      const playCall = calls.find(([input, init]) => toUrl(input).pathname === "/api/jobs/play" && (init?.method ?? "GET").toUpperCase() === "POST");
      expect(playCall).toBeDefined();
    });
  });
});

function toUrl(input: RequestInfo | URL): URL {
  if (typeof input === "string") {
    return new URL(input, "http://127.0.0.1");
  }
  if (input instanceof URL) {
    return input;
  }
  return new URL(input.url, "http://127.0.0.1");
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
