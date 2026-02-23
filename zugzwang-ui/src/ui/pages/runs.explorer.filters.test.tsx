import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { router } from "../../router";

describe("runs explorer filters and compare selection", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = toUrl(input);
      const pathname = url.pathname;
      const method = (init?.method ?? "GET").toUpperCase();

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
          {
            provider: "openai",
            provider_label: "OpenAI",
            api_style: "openai_chat_completions",
            base_url: "https://api.openai.com/v1",
            api_key_env: "OPENAI_API_KEY",
            notes: "test preset",
            models: [{ id: "gpt-5", label: "GPT-5", recommended: true }],
          },
        ]);
      }

      if (pathname === "/api/runs" && method === "GET") {
        return jsonResponse([
          {
            run_id: "run-openai-1",
            run_dir: "results/runs/run-openai-1",
            created_at_utc: "2026-02-22T00:00:00Z",
            config_hash: "abc123",
            report_exists: true,
            evaluated_report_exists: true,
            inferred_provider: "openai",
            inferred_model_label: "OpenAI / GPT-5",
            inferred_eval_status: "evaluated",
            num_games_valid: 10,
            num_games_target: 10,
            total_cost_usd: 1.23,
            elo_estimate: 700.2,
            acpl_overall: 45.1,
          },
          {
            run_id: "run-openai-2",
            run_dir: "results/runs/run-openai-2",
            created_at_utc: "2026-02-23T00:00:00Z",
            config_hash: "def456",
            report_exists: true,
            evaluated_report_exists: false,
            inferred_provider: "openai",
            inferred_model_label: "OpenAI / GPT-5",
            inferred_eval_status: "needs_eval",
            num_games_valid: 5,
            num_games_target: 10,
            total_cost_usd: 0.76,
            elo_estimate: null,
            acpl_overall: null,
          },
        ]);
      }

      if (pathname === "/api/runs/run-openai-1" && method === "GET") {
        return jsonResponse({
          run_meta: {
            run_id: "run-openai-1",
            run_dir: "results/runs/run-openai-1",
            created_at_utc: "2026-02-22T00:00:00Z",
            config_hash: "abc123",
            report_exists: true,
            evaluated_report_exists: true,
          },
          report: {},
          evaluated_report: {},
          game_count: 1,
        });
      }

      if (pathname === "/api/runs/run-openai-2" && method === "GET") {
        return jsonResponse({
          run_meta: {
            run_id: "run-openai-2",
            run_dir: "results/runs/run-openai-2",
            created_at_utc: "2026-02-23T00:00:00Z",
            config_hash: "def456",
            report_exists: true,
            evaluated_report_exists: false,
          },
          report: {},
          evaluated_report: {},
          game_count: 1,
        });
      }

      if (pathname === "/api/runs/run-openai-1/games" && method === "GET") {
        return jsonResponse([]);
      }

      if (pathname === "/api/runs/run-openai-2/games" && method === "GET") {
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

  it("applies filters and enables compare selected flow", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
        },
      },
    });

    await router.navigate({ to: "/runs" });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await screen.findByRole("heading", { name: "Run Explorer" });
    const user = userEvent.setup();
    await screen.findByRole("option", { name: "openai" });

    await user.selectOptions(screen.getByLabelText("Provider"), "openai");
    await user.click(screen.getByLabelText("Evaluated only"));
    await user.click(screen.getByRole("button", { name: "Elo" }));
    await user.click(screen.getByLabelText("Select run-openai-1 for comparison"));
    await user.click(screen.getByLabelText("Select run-openai-2 for comparison"));

    const compareButton = screen.getByRole("button", { name: /Compare Selected \(2\)/ });
    expect(compareButton).toBeEnabled();
    await user.click(compareButton);

    await screen.findByRole("heading", { name: "Compare Workbench" });

    await waitFor(() => {
      const calls = vi.mocked(globalThis.fetch).mock.calls.map(([input]) => toUrl(input));
      const filteredRunsCall = calls.find(
        (url) =>
          url.pathname === "/api/runs" &&
          url.searchParams.get("provider") === "openai" &&
          url.searchParams.get("evaluated_only") === "true" &&
          url.searchParams.get("sort_by") === "elo_estimate",
      );
      expect(filteredRunsCall).toBeDefined();
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
