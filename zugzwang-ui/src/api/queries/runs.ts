import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../client";
import type { RunListItem, RunSummaryResponse } from "../types";

type RunsFilters = {
  q?: string;
  evaluatedOnly?: boolean;
};

export function useRuns(filters: RunsFilters = {}) {
  const params = new URLSearchParams();
  if (filters.q?.trim()) {
    params.set("q", filters.q.trim());
  }
  if (filters.evaluatedOnly) {
    params.set("evaluated_only", "true");
  }

  const queryString = params.toString();
  const path = queryString ? `/api/runs?${queryString}` : "/api/runs";

  return useQuery({
    queryKey: ["runs", filters] as const,
    queryFn: () => apiRequest<RunListItem[]>(path),
    staleTime: 10_000,
  });
}

export function useRunSummary(runId: string | null) {
  return useQuery({
    queryKey: ["run-summary", runId] as const,
    queryFn: () => apiRequest<RunSummaryResponse>(`/api/runs/${runId}`),
    enabled: Boolean(runId),
    staleTime: 30_000,
  });
}

