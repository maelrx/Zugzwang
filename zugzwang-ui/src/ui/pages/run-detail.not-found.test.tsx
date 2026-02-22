import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { router } from "../../router";

const RUN_ID = "qa_run_cancel_20260222143457-20260222T173539Z-e597406e";

describe("run detail missing artifacts", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = toUrl(input);
      if (url.pathname === `/api/runs/${RUN_ID}`) {
        return jsonResponse({ detail: `Run directory not found: ${RUN_ID}` }, 404);
      }
      return jsonResponse({ detail: `Unhandled mock route: ${url.pathname}` }, 404);
    });
  });

  afterEach(async () => {
    cleanup();
    vi.restoreAllMocks();
    await router.navigate({ to: "/" });
  });

  it("shows contextual message and avoids games request when run summary is 404", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          refetchOnWindowFocus: false,
        },
      },
    });

    await router.navigate({ to: `/runs/${RUN_ID}` });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await screen.findByText("Artifacts for this run are not available yet. This usually happens when a job is canceled before the first files are written.");

    await waitFor(() => {
      const paths = vi
        .mocked(globalThis.fetch)
        .mock.calls.map(([input]) => toUrl(input).pathname);
      expect(paths).toContain(`/api/runs/${RUN_ID}`);
      expect(paths).not.toContain(`/api/runs/${RUN_ID}/games`);
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
