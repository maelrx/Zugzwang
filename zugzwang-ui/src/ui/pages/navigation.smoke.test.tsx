import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-chessboard", () => ({
  Chessboard: () => <div data-testid="mock-chessboard">mock-chessboard</div>,
}));

import { router } from "../../router";

const RUN_ID = "test_run-20260222T000000Z-abc12345";

describe("navigation smoke", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = toUrl(input);
      const pathname = url.pathname;

      if (pathname === "/api/jobs") {
        return jsonResponse([
          {
            job_id: "job-smoke-1",
            job_type: "run",
            status: "completed",
            pid: null,
            command: ["python", "-m", "zugzwang.cli", "run"],
            created_at_utc: "2026-02-22T00:00:00Z",
            updated_at_utc: "2026-02-22T00:00:10Z",
            stdout_path: "results/ui_jobs/logs/job-smoke-1.stdout.log",
            stderr_path: "results/ui_jobs/logs/job-smoke-1.stderr.log",
            run_id: RUN_ID,
            run_dir: `results/runs/${RUN_ID}`,
            meta: {},
            result_payload: null,
            exit_code: 0,
          },
        ]);
      }

      if (pathname === "/api/env-check") {
        return jsonResponse([
          { provider: "zai", ok: true, message: "ZAI_API_KEY set" },
          { provider: "stockfish", ok: true, message: "STOCKFISH_PATH set" },
        ]);
      }

      if (pathname === "/api/configs") {
        return jsonResponse({
          baselines: [{ name: "best_known_start", path: "configs/baselines/best_known_start.yaml", category: "baselines" }],
          ablations: [],
        });
      }

      if (pathname === "/api/configs/model-catalog") {
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

      if (pathname === "/api/runs") {
        return jsonResponse([
          {
            run_id: RUN_ID,
            run_dir: `results/runs/${RUN_ID}`,
            created_at_utc: "2026-02-22T00:00:00Z",
            config_hash: "abc123",
            report_exists: true,
            evaluated_report_exists: true,
            inferred_model_label: "zai / glm-5",
            inferred_eval_status: "evaluated",
            num_games_valid: 1,
            num_games_target: 1,
            total_cost_usd: 0.03,
            elo_estimate: 630.0,
          },
        ]);
      }

      if (pathname === "/api/dashboard/kpis") {
        return jsonResponse({
          total_runs: 1,
          runs_with_reports: 1,
          evaluated_runs: 1,
          best_elo: 630.0,
          avg_acpl: 20.0,
          total_cost_usd: 0.03,
          last_run_id: RUN_ID,
          timeline: [
            {
              run_id: RUN_ID,
              created_at_utc: "2026-02-22T00:00:00Z",
              inferred_model_label: "zai / glm-5",
              total_cost_usd: 0.03,
              elo_estimate: 630.0,
              acpl_overall: 20.0,
              evaluated_report_exists: true,
            },
          ],
        });
      }

      if (pathname === `/api/runs/${RUN_ID}`) {
        return jsonResponse({
          run_meta: {
            run_id: RUN_ID,
            run_dir: `results/runs/${RUN_ID}`,
            created_at_utc: "2026-02-22T00:00:00Z",
            config_hash: "abc123",
            report_exists: true,
            evaluated_report_exists: true,
          },
          resolved_config: {
            experiment: { target_valid_games: 1 },
          },
          report: {
            num_games_target: 1,
            num_games_valid: 1,
            completion_rate: 1.0,
            total_cost_usd: 0.03,
            acpl_overall: 20.0,
            acpl_by_phase: { opening: 20.0, middlegame: 0.0, endgame: 0.0 },
            blunder_rate: 0.0,
            best_move_agreement: 0.5,
            retrieval_hit_rate: 0.6,
            retrieval_hit_rate_by_phase: { opening: 0.7, middlegame: 0.4, endgame: 0.0 },
            avg_tokens_per_move: 120.0,
            p95_move_latency_ms: 2100.0,
            stopped_due_to_budget: false,
            budget_stop_reason: null,
          },
          evaluated_report: {
            acpl_overall: 20.0,
            acpl_by_phase: { opening: 20.0, middlegame: 0.0, endgame: 0.0 },
            blunder_rate: 0.0,
            best_move_agreement: 0.5,
            retrieval_hit_rate: 0.6,
            retrieval_hit_rate_by_phase: { opening: 0.7, middlegame: 0.4, endgame: 0.0 },
            avg_tokens_per_move: 120.0,
            p95_move_latency_ms: 2100.0,
            stopped_due_to_budget: false,
            budget_stop_reason: null,
            evaluation: {
              provider: "stockfish",
              player_color: "black",
              stockfish: { depth: 12 },
            },
          },
          game_count: 1,
        });
      }

      if (pathname === `/api/runs/${RUN_ID}/games`) {
        return jsonResponse([{ game_number: 1, path: `results/runs/${RUN_ID}/games/game_0001.json` }]);
      }

      if (pathname === `/api/runs/${RUN_ID}/games/1/frames`) {
        return jsonResponse([
          {
            ply_number: 0,
            fen: "start",
            svg: "<svg></svg>",
            move_uci: null,
            move_san: null,
            color: null,
            raw_response: null,
          },
          {
            ply_number: 1,
            fen: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            svg: "<svg></svg>",
            move_uci: "e2e4",
            move_san: "e4",
            color: "white",
            raw_response: "e2e4",
          },
          {
            ply_number: 2,
            fen: "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            svg: "<svg></svg>",
            move_uci: "e7e5",
            move_san: "e5",
            color: "black",
            raw_response: "e7e5",
          },
        ]);
      }

      if (pathname === `/api/runs/${RUN_ID}/games/1`) {
        return jsonResponse({
          game_number: 1,
          result: "1-0",
          termination: "checkmate",
          duration_seconds: 12.5,
          total_cost_usd: 0.03,
          total_tokens: { input: 300, output: 60 },
          moves: [
            {
              ply_number: 1,
              move_decision: {
                move_uci: "e2e4",
                move_san: "e4",
                parse_ok: true,
                is_legal: true,
                retry_count: 0,
                latency_ms: 1000,
                tokens_input: 100,
                tokens_output: 20,
                cost_usd: 0.01,
                provider_model: "glm-5",
              },
            },
            {
              ply_number: 2,
              move_decision: {
                move_uci: "e7e5",
                move_san: "e5",
                parse_ok: true,
                is_legal: true,
                retry_count: 1,
                latency_ms: 1100,
                tokens_input: 90,
                tokens_output: 18,
                cost_usd: 0.01,
                provider_model: "glm-5",
              },
            },
          ],
        });
      }

      return jsonResponse({ detail: `Unhandled mock route: ${pathname}` }, 404);
    });
  });

  afterEach(async () => {
    cleanup();
    vi.restoreAllMocks();
    await router.navigate({ to: "/" });
  });

  it("navigates across core pages without runtime failures", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
        },
      },
    });

    await router.navigate({ to: "/" });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    const user = userEvent.setup();

    await screen.findByRole("heading", { name: "Command Center" });

    await user.click(screen.getByRole("link", { name: "Experiment Lab" }));
    await screen.findByRole("heading", { name: "Experiment Launch Workbench" });

    await user.click(screen.getByRole("link", { name: "Quick Play" }));
    await screen.findByRole("heading", { name: "Quick Play" });

    await user.click(screen.getByRole("link", { name: "Runs" }));
    await screen.findByRole("heading", { name: "Run Explorer" });

    await user.click(await screen.findByRole("link", { name: RUN_ID }));
    await screen.findByRole("heading", { name: RUN_ID });
    await user.click(screen.getByRole("button", { name: "Games" }));

    await user.click(await screen.findByRole("link", { name: "Full Analysis" }));
    await screen.findByRole("heading", { name: new RegExp(`${RUN_ID} / game 1`) });

    await user.click(screen.getByRole("link", { name: "Settings" }));
    await screen.findByRole("heading", { name: "Environment Diagnostics" });

    await user.click(screen.getByRole("link", { name: "Compare" }));
    await screen.findByRole("heading", { name: "Run Comparison" });

    expect(screen.getByText("Select two runs to populate comparison metrics.")).toBeInTheDocument();
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
