import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { router } from "../../router";

describe("run lab research presets", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = toUrl(input);
      const pathname = url.pathname;
      const method = (init?.method ?? "GET").toUpperCase();

      if (pathname === "/api/configs" && method === "GET") {
        return jsonResponse({
          baselines: [{ name: "best_known_start", path: "configs/baselines/best_known_start.yaml", category: "baselines" }],
          ablations: [
            {
              name: "prompt_structured_analysis",
              path: "D:/Zugzwang - Chess LLM Engine/zugzwang-engine/configs/ablations/prompt_structured_analysis.yaml",
              category: "ablations",
            },
          ],
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

      if (pathname === "/api/configs/validate" && method === "POST") {
        return jsonResponse({
          ok: true,
          message: "valid",
          config_hash: "cfg-hash-1",
          resolved_config: { experiment: { target_valid_games: 10 } },
        });
      }

      if (pathname === "/api/configs/preview" && method === "POST") {
        return jsonResponse({
          config_path: "configs/ablations/prompt_structured_analysis.yaml",
          config_hash: "cfg-hash-1",
          run_id: "run-preview-1",
          scheduled_games: 10,
          estimated_total_cost_usd: 0.25,
          resolved_config: { experiment: { target_valid_games: 10 } },
        });
      }

      if (pathname === "/api/jobs" && method === "GET") {
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

  it("applies prompt_ablation preset when template path arrives as absolute path", async () => {
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
    await user.click(screen.getByRole("button", { name: /prompt_ablation/i }));

    expect(
      await screen.findByText(/Preset prompt_ablation applied with 16 target games using .*prompt_structured_analysis\.yaml\./),
    ).toBeInTheDocument();
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
