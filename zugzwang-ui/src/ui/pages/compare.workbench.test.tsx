import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { router } from "../../router";

describe("compare workbench", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = toUrl(input);
      const pathname = url.pathname;
      const method = (init?.method ?? "GET").toUpperCase();

      if (pathname === "/api/runs" && method === "GET") {
        return jsonResponse([
          {
            run_id: "run-a",
            run_dir: "results/runs/run-a",
            created_at_utc: "2026-02-22T00:00:00Z",
            config_hash: "aaa",
            report_exists: true,
            evaluated_report_exists: true,
            inferred_provider: "zai",
            inferred_model_label: "zai / glm-5",
            inferred_eval_status: "evaluated",
          },
          {
            run_id: "run-b",
            run_dir: "results/runs/run-b",
            created_at_utc: "2026-02-23T00:00:00Z",
            config_hash: "bbb",
            report_exists: true,
            evaluated_report_exists: true,
            inferred_provider: "openai",
            inferred_model_label: "openai / gpt-5",
            inferred_eval_status: "evaluated",
          },
        ]);
      }

      if (pathname === "/api/runs/run-a" && method === "GET") {
        return jsonResponse({
          run_meta: {
            run_id: "run-a",
            run_dir: "results/runs/run-a",
            created_at_utc: "2026-02-22T00:00:00Z",
            config_hash: "aaa",
            report_exists: true,
            evaluated_report_exists: true,
          },
          resolved_config: {
            strategy: {
              provide_history: true,
              board_format: "fen",
            },
          },
          report: {
            num_games_target: 10,
            num_games_valid: 10,
            completion_rate: 1.0,
            total_cost_usd: 1.2,
            acpl_overall: 120,
            acpl_by_phase: { opening: 80, middlegame: 140, endgame: 200 },
            blunder_rate: 0.12,
            best_move_agreement: 0.34,
            p95_move_latency_ms: 1400,
          },
          evaluated_report: {
            acpl_overall: 120,
            acpl_by_phase: { opening: 80, middlegame: 140, endgame: 200 },
            blunder_rate: 0.12,
            best_move_agreement: 0.34,
            elo_estimate: 610,
          },
          game_count: 1,
        });
      }

      if (pathname === "/api/runs/run-b" && method === "GET") {
        return jsonResponse({
          run_meta: {
            run_id: "run-b",
            run_dir: "results/runs/run-b",
            created_at_utc: "2026-02-23T00:00:00Z",
            config_hash: "bbb",
            report_exists: true,
            evaluated_report_exists: true,
          },
          resolved_config: {
            strategy: {
              provide_history: false,
              board_format: "pgn",
            },
          },
          report: {
            num_games_target: 10,
            num_games_valid: 10,
            completion_rate: 1.0,
            total_cost_usd: 2.0,
            acpl_overall: 90,
            acpl_by_phase: { opening: 70, middlegame: 100, endgame: 140 },
            blunder_rate: 0.08,
            best_move_agreement: 0.41,
            p95_move_latency_ms: 2100,
          },
          evaluated_report: {
            acpl_overall: 90,
            acpl_by_phase: { opening: 70, middlegame: 100, endgame: 140 },
            blunder_rate: 0.08,
            best_move_agreement: 0.41,
            elo_estimate: 720,
          },
          game_count: 1,
        });
      }

      if (pathname === "/api/runs/run-a/games" && method === "GET") {
        return jsonResponse([]);
      }

      if (pathname === "/api/runs/run-b/games" && method === "GET") {
        return jsonResponse([]);
      }

      return jsonResponse({ detail: `Unhandled mock route: ${method} ${pathname}` }, 404);
    });
  });

  afterEach(async () => {
    cleanup();
    vi.restoreAllMocks();
    await router.navigate({ to: "/" });
  });

  it("loads selected runs from URL and renders config diff", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
        },
      },
    });

    await router.navigate({ to: "/compare" });
    window.history.replaceState(null, "", "/compare?runs=run-a,run-b");

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await screen.findByRole("heading", { name: "Compare Workbench" });
    await screen.findByText("Config Diff");
    await screen.findByText("strategy.provide_history");
    await screen.findByText("strategy.board_format");
    await screen.findByText("Cost per game (USD)");

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /run-b x/i }));
    expect(screen.getByText("Select at least 2 runs to populate the comparison table.")).toBeInTheDocument();
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
