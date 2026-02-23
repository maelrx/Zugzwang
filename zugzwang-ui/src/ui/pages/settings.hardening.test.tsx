import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { router } from "../../router";

describe("settings hardening", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = toUrl(input);
      const pathname = url.pathname;
      const method = (init?.method ?? "GET").toUpperCase();

      if (pathname === "/api/jobs" && method === "GET") {
        return jsonResponse([
          {
            job_id: "job-run-1",
            job_type: "run",
            status: "running",
            pid: 1111,
            command: ["python", "-m", "zugzwang"],
            created_at_utc: "2026-02-23T00:00:00Z",
            updated_at_utc: "2026-02-23T00:01:00Z",
            stdout_path: "logs/job-run-1.out",
            stderr_path: "logs/job-run-1.err",
            run_id: "run-live-1",
            run_dir: "results/runs/run-live-1",
          },
          {
            job_id: "job-eval-1",
            job_type: "evaluate",
            status: "running",
            pid: 1112,
            command: ["python", "-m", "zugzwang"],
            created_at_utc: "2026-02-23T00:00:10Z",
            updated_at_utc: "2026-02-23T00:01:10Z",
            stdout_path: "logs/job-eval-1.out",
            stderr_path: "logs/job-eval-1.err",
            run_id: "run-live-2",
            run_dir: "results/runs/run-live-2",
          },
        ]);
      }

      if (pathname === "/api/jobs/job-run-1/progress" && method === "GET") {
        return jsonResponse({
          job_id: "job-run-1",
          status: "running",
          games_written: 4,
          games_target: 10,
          latest_report: null,
          finished_at_utc: null,
          run_id: "run-live-1",
        });
      }

      if (pathname === "/api/jobs/job-eval-1/progress" && method === "GET") {
        return jsonResponse({
          job_id: "job-eval-1",
          status: "running",
          games_written: 1,
          games_target: 1,
          latest_report: null,
          finished_at_utc: null,
          run_id: "run-live-2",
        });
      }

      if (pathname === "/api/env-check" && method === "GET") {
        return jsonResponse([
          { provider: "openai", ok: true, message: "OPENAI_API_KEY set" },
          { provider: "anthropic", ok: false, message: "ANTHROPIC_API_KEY missing" },
          { provider: "stockfish", ok: true, message: "STOCKFISH_PATH set" },
        ]);
      }

      if (pathname === "/api/configs/model-catalog" && method === "GET") {
        return jsonResponse([
          {
            provider: "openai",
            provider_label: "OpenAI",
            api_style: "openai",
            base_url: "https://api.openai.com",
            api_key_env: "OPENAI_API_KEY",
            notes: "",
            models: [
              { id: "gpt-5", label: "gpt-5", recommended: true },
              { id: "gpt-4o", label: "gpt-4o", recommended: false },
            ],
          },
          {
            provider: "anthropic",
            provider_label: "Anthropic",
            api_style: "openai",
            base_url: "https://api.anthropic.com",
            api_key_env: "ANTHROPIC_API_KEY",
            notes: "",
            models: [{ id: "claude-opus", label: "claude-opus", recommended: true }],
          },
        ]);
      }

      return jsonResponse({ detail: `Unhandled mock route: ${method} ${pathname}` }, 404);
    });
  });

  afterEach(async () => {
    cleanup();
    vi.restoreAllMocks();
    await router.navigate({ to: "/" });
  });

  it("renders sidebar active jobs panel and persists settings preferences", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
        },
      },
    });

    await router.navigate({ to: "/settings" });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await screen.findByRole("heading", { name: "Environment Diagnostics" });
    await screen.findByText("Providers Health");
    await screen.findByText("Stockfish");
    await screen.findByText("Preferences");

    expect(screen.getByRole("link", { name: /Command Center/i })).toHaveTextContent("2");

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Active Jobs/i }));
    await screen.findByText("run-live-1");
    await screen.findByText("run-live-2");

    await user.selectOptions(screen.getByLabelText("Default provider"), "anthropic");
    await user.selectOptions(screen.getByLabelText("Default model"), "claude-opus");
    await user.click(screen.getByRole("checkbox", { name: "Notifications" }));
    await user.click(screen.getByRole("checkbox", { name: "Auto-evaluate by default" }));
    const depthInput = screen.getByRole("spinbutton", { name: "Default evaluation depth" });
    fireEvent.change(depthInput, { target: { value: "18" } });
    await user.selectOptions(screen.getByLabelText("Engine resources mode"), "manual");
    const threadsInput = screen.getByRole("spinbutton", { name: "Manual Stockfish threads" });
    fireEvent.change(threadsInput, { target: { value: "6" } });
    const hashInput = screen.getByRole("spinbutton", { name: "Manual Stockfish hash (MB)" });
    fireEvent.change(hashInput, { target: { value: "768" } });

    const rawPersisted = window.localStorage.getItem("zugzwang-preferences-v2");
    expect(rawPersisted).not.toBeNull();
    const persisted = JSON.parse(rawPersisted ?? "{}");
    expect(persisted.version).toBe(3);
    expect(persisted.state.defaultProvider).toBe("anthropic");
    expect(persisted.state.defaultModel).toBe("claude-opus");
    expect(persisted.state.notificationsEnabled).toBe(false);
    expect(persisted.state.autoEvaluate).toBe(false);
    expect(persisted.state.stockfishDepth).toBe(18);
    expect(persisted.state.stockfishResourceMode).toBe("manual");
    expect(persisted.state.stockfishThreads).toBe(6);
    expect(persisted.state.stockfishHashMb).toBe(768);
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
