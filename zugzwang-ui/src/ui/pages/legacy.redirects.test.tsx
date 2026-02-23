import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { router } from "../../router";

const RUN_ID = "legacy-run-20260223T000000Z";

describe("legacy redirects", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = toUrl(input);
      const pathname = url.pathname;
      const method = (init?.method ?? "GET").toUpperCase();

      if (pathname === "/api/jobs" && method === "GET") {
        return jsonResponse([]);
      }

      if (pathname === "/api/env-check" && method === "GET") {
        return jsonResponse([
          { provider: "zai", ok: true, message: "ZAI_API_KEY set" },
          { provider: "stockfish", ok: true, message: "STOCKFISH_PATH set" },
        ]);
      }

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
            base_url: "https://api.z.ai",
            api_key_env: "ZAI_API_KEY",
            notes: "",
            models: [{ id: "glm-5", label: "GLM-5", recommended: true }],
          },
        ]);
      }

      if (pathname === "/api/runs" && method === "GET") {
        return jsonResponse([
          {
            run_id: RUN_ID,
            run_dir: `results/runs/${RUN_ID}`,
            created_at_utc: "2026-02-23T00:00:00Z",
            config_hash: "legacy",
            report_exists: true,
            evaluated_report_exists: true,
            inferred_model_label: "zai / glm-5",
            inferred_eval_status: "evaluated",
          },
        ]);
      }

      if (pathname === `/api/runs/${RUN_ID}` && method === "GET") {
        return jsonResponse({
          run_meta: {
            run_id: RUN_ID,
            run_dir: `results/runs/${RUN_ID}`,
            created_at_utc: "2026-02-23T00:00:00Z",
            config_hash: "legacy",
            report_exists: true,
            evaluated_report_exists: true,
          },
          resolved_config: {},
          report: {
            num_games_target: 1,
            num_games_valid: 1,
            completion_rate: 1.0,
            total_cost_usd: 0.01,
            acpl_overall: 60,
            acpl_by_phase: { opening: 60, middlegame: 0, endgame: 0 },
            blunder_rate: 0.0,
            best_move_agreement: 0.5,
            p95_move_latency_ms: 1200,
          },
          evaluated_report: {
            acpl_overall: 60,
            acpl_by_phase: { opening: 60, middlegame: 0, endgame: 0 },
            blunder_rate: 0.0,
            best_move_agreement: 0.5,
            elo_estimate: 700,
          },
          game_count: 1,
        });
      }

      if (pathname === `/api/runs/${RUN_ID}/games` && method === "GET") {
        return jsonResponse([{ game_number: 1, path: `results/runs/${RUN_ID}/games/game_0001.json` }]);
      }

      if (pathname === `/api/runs/${RUN_ID}/games/1` && method === "GET") {
        return jsonResponse({
          game_number: 1,
          result: "1-0",
          termination: "checkmate",
          duration_seconds: 10.5,
          total_cost_usd: 0.01,
          total_tokens: { input: 100, output: 30 },
          moves: [],
        });
      }

      if (pathname === `/api/runs/${RUN_ID}/games/1/frames` && method === "GET") {
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

  it("redirects legacy routes to canonical v2 routes", async () => {
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

    await router.navigate({ to: "/run-lab" });
    await screen.findByRole("heading", { name: "Experiment Launch Workbench" });
    await waitFor(() => expect(window.location.pathname).toBe("/lab"));

    await router.navigate({ to: "/runs/compare" });
    await screen.findByRole("heading", { name: "Compare Workbench" });
    await waitFor(() => expect(window.location.pathname).toBe("/compare"));

    await router.navigate({
      to: "/runs/$runId/replay/$gameNumber",
      params: { runId: RUN_ID, gameNumber: "1" },
    });
    await screen.findByRole("heading", { name: new RegExp(`${RUN_ID} / game 1`) });
    await waitFor(() => expect(window.location.pathname).toBe(`/runs/${RUN_ID}/game/1`));
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
