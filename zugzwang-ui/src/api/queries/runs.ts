import { useQuery } from "@tanstack/react-query";
import { ApiError, apiRequest } from "../client";
import type { BoardFrameResponse, GameDetailResponse, GameListItem, RunListItem, RunSummaryResponse } from "../types";

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
    retry: shouldRetry,
  });
}

export function useRunGames(runId: string | null, enabled = true) {
  return useQuery({
    queryKey: ["run-games", runId] as const,
    queryFn: () => apiRequest<GameListItem[]>(`/api/runs/${runId}/games`),
    enabled: Boolean(runId) && enabled,
    staleTime: 60_000,
    retry: shouldRetry,
  });
}

export function useGame(runId: string | null, gameNumber: number | null) {
  return useQuery({
    queryKey: ["game", runId, gameNumber] as const,
    queryFn: () => apiRequest<GameDetailResponse>(`/api/runs/${runId}/games/${gameNumber}`),
    enabled: Boolean(runId) && gameNumber !== null,
    staleTime: 60_000,
    retry: shouldRetry,
  });
}

export function useGameFrames(runId: string | null, gameNumber: number | null) {
  return useQuery({
    queryKey: ["game-frames", runId, gameNumber] as const,
    queryFn: () => apiRequest<BoardFrameResponse[]>(`/api/runs/${runId}/games/${gameNumber}/frames`),
    enabled: Boolean(runId) && gameNumber !== null,
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status === 404) {
    return false;
  }
  return failureCount < 2;
}
