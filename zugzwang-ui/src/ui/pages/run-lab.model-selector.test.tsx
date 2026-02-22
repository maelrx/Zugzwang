import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { router } from "../../router";

describe("run lab model selector", () => {
  beforeEach(() => {
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
          {
            provider: "openai",
            provider_label: "OpenAI (GPT)",
            api_style: "openai_chat_completions",
            base_url: "https://api.openai.com/v1",
            api_key_env: "OPENAI_API_KEY",
            notes: "test preset",
            models: [{ id: "gpt-5", label: "GPT-5", recommended: true }],
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

  it("applies selected provider/model as black-player overrides", async () => {
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
    await screen.findByRole("option", { name: /OpenAI/ });
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("Provider"), "openai");
    await user.selectOptions(screen.getByLabelText("Model"), "gpt-5");
    await user.click(screen.getByRole("button", { name: "Apply Preset to Overrides" }));

    const overrides = screen.getByLabelText("Overrides (`key=value`, one per line)") as HTMLTextAreaElement;
    expect(overrides.value).toContain("players.black.type=llm");
    expect(overrides.value).toContain("players.black.provider=openai");
    expect(overrides.value).toContain("players.black.model=gpt-5");
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
