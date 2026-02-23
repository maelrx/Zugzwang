import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { router } from "../../router";

type Listener = (event: { data: string }) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly url: string;
  private listeners = new Map<string, Listener[]>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    const current = this.listeners.get(type) ?? [];
    current.push(listener);
    this.listeners.set(type, current);
  }

  close() {
    // no-op in tests
  }

  emit(type: string, data: string) {
    const current = this.listeners.get(type) ?? [];
    for (const listener of current) {
      listener({ data });
    }
  }
}

describe("job detail log stream", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const pathname = toUrl(input).pathname;

      if (pathname === "/api/jobs/job-sse-1") {
        return jsonResponse({
          job_id: "job-sse-1",
          job_type: "run",
          status: "running",
          pid: 123,
          command: ["python", "-m", "zugzwang.cli", "run"],
          created_at_utc: "2026-02-22T00:00:00Z",
          updated_at_utc: null,
          stdout_path: "results/ui_jobs/logs/job-sse-1.stdout.log",
          stderr_path: "results/ui_jobs/logs/job-sse-1.stderr.log",
          run_id: "run-sse-1",
          run_dir: "results/runs/run-sse-1",
          meta: {},
          result_payload: null,
          exit_code: null,
        });
      }

      if (pathname === "/api/jobs/job-sse-1/progress") {
        return jsonResponse({
          run_id: "run-sse-1",
          status: "running",
          games_written: 0,
          games_target: 1,
          run_dir: "results/runs/run-sse-1",
          stopped_due_to_budget: false,
          budget_stop_reason: null,
          latest_report: null,
          log_tail: "",
        });
      }

      return jsonResponse({ detail: `Unhandled mock route: ${pathname}` }, 404);
    });
  });

  afterEach(async () => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    await router.navigate({ to: "/" });
  });

  it("renders stdout/stderr events and done sentinel from SSE stream", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
        },
      },
    });

    await router.navigate({ to: "/dashboard/jobs/$jobId", params: { jobId: "job-sse-1" } });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await screen.findByRole("heading", { name: "Job job-sse-1" });
    expect(FakeEventSource.instances.length).toBeGreaterThan(0);

    const stream = FakeEventSource.instances[0];
    stream.emit("stdout", "line from stdout");
    stream.emit("stderr", "line from stderr");
    stream.emit("done", JSON.stringify({ status: "completed" }));

    await screen.findByText("line from stdout");
    await screen.findByText("line from stderr");
    await screen.findByText("[stream closed: completed]");
    expect(screen.getByText("done")).toBeInTheDocument();
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
