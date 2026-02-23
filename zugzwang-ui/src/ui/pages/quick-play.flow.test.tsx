import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-chessboard", () => ({
  Chessboard: () => <div data-testid="mock-chessboard">mock-chessboard</div>,
}));

import { router } from "../../router";

describe("quick play flow", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    let jobsVisible = false;

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

      if (pathname === "/api/configs/model-catalog" && method === "GET") {
        return jsonResponse([
          {
            provider: "zai",
            provider_label: "z.ai (GLM)",
            api_style: "openai_chat_completions",
            base_url: "https://api.z.ai/api/coding/paas/v4",
            api_key_env: "ZAI_API_KEY",
            notes: "test preset",
            models: [{ id: "glm-5", label: "GLM-5", recommended: true }],
          },
        ]);
      }

      if (pathname === "/api/env-check" && method === "GET") {
        return jsonResponse([
          { provider: "zai", ok: true, message: "configured" },
          { provider: "stockfish", ok: true, message: "configured" },
        ]);
      }

      if (pathname === "/api/jobs" && method === "GET") {
        if (!jobsVisible) {
          return jsonResponse([]);
        }
        return jsonResponse([
          {
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
          },
        ]);
      }

      if (pathname === "/api/jobs/play" && method === "POST") {
        jobsVisible = true;
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
          latest_report: { total_cost_usd: 0.02 },
          log_tail: "",
        });
      }

      if (pathname === "/api/runs/run-play-1/games" && method === "GET") {
        return jsonResponse([{ game_number: 1, path: "results/runs/run-play-1/games/game_0001.json" }]);
      }

      if (pathname === "/api/runs/run-play-1/games/1" && method === "GET") {
        return jsonResponse({
          game_number: 1,
          result: "1-0",
          termination: "checkmate",
          duration_seconds: 9.5,
          total_cost_usd: 0.02,
          total_tokens: { input: 120, output: 30 },
          moves: [
            { ply_number: 1, move_decision: { move_uci: "e2e4", move_san: "e4" } },
            { ply_number: 2, move_decision: { move_uci: "e7e5", move_san: "e5" } },
          ],
        });
      }

      if (pathname === "/api/runs/run-play-1/games/1/frames" && method === "GET") {
        return jsonResponse([
          { ply_number: 0, fen: "start", svg: "<svg />", move_uci: null, move_san: null, color: null, raw_response: null },
          { ply_number: 1, fen: "after", svg: "<svg />", move_uci: "e2e4", move_san: "e4", color: "white", raw_response: "e2e4" },
        ]);
      }

      if (pathname === "/api/runs/run-play-1" && method === "GET") {
        return jsonResponse({
          run_meta: {
            run_id: "run-play-1",
            run_dir: "results/runs/run-play-1",
            created_at_utc: "2026-02-22T00:00:00Z",
            config_hash: "abc123",
            report_exists: true,
            evaluated_report_exists: true,
          },
          report: { num_games_target: 1, num_games_valid: 1, total_cost_usd: 0.02 },
          evaluated_report: {
            acpl_overall: 32.0,
            blunder_rate: 0.05,
            best_move_agreement: 0.45,
          },
          game_count: 1,
        });
      }

      return jsonResponse({ detail: `Unhandled mock route: ${method} ${pathname}` }, 404);
    });
  });

  afterEach(async () => {
    cleanup();
    vi.restoreAllMocks();
    await router.navigate({ to: "/" });
  });

  it("launches quick play and renders post-game summary", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
        },
      },
    });

    await router.navigate({ to: "/quick-play" });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Quick Play" });
    await user.click(screen.getByRole("button", { name: "Show advanced options" }));
    await user.selectOptions(screen.getByLabelText("Opponent"), "stockfish");
    await user.click(screen.getByRole("button", { name: "Play Game" }));

    await screen.findByText("Result summary");
    expect(screen.getByText(/checkmate/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Full Analysis" })).toBeInTheDocument();

    await waitFor(() => {
      const calls = vi.mocked(globalThis.fetch).mock.calls;
      const playCall = calls.find(([input, init]) => toUrl(input).pathname === "/api/jobs/play" && (init?.method ?? "GET").toUpperCase() === "POST");
      expect(playCall).toBeDefined();
      const requestInit = playCall?.[1] as RequestInit | undefined;
      const payload = requestInit?.body ? JSON.parse(String(requestInit.body)) : {};
      const overrides = Array.isArray(payload.overrides) ? payload.overrides : [];
      expect(overrides).toContain("players.black.provider=zai");
      expect(overrides).toContain("players.black.model=glm-5");
      expect(overrides).toContain("evaluation.auto.enabled=true");
      expect(overrides).toContain("players.white.type=engine");
    });

    await waitFor(() => {
      const jobsCalls = vi
        .mocked(globalThis.fetch)
        .mock.calls.filter(([input, init]) => toUrl(input).pathname === "/api/jobs" && (init?.method ?? "GET").toUpperCase() === "GET");
      expect(jobsCalls.length).toBeGreaterThanOrEqual(2);
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
