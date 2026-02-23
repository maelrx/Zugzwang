import { useMutation, useQuery } from "@tanstack/react-query";
import { apiRequest } from "../client";
import type { AnalysisCompareRequest, AnalysisCompareResponse } from "../types";

export function useCreateRunComparison() {
  return useMutation({
    mutationFn: (payload: AnalysisCompareRequest) =>
      apiRequest<AnalysisCompareResponse>("/api/analysis/compare", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useRunComparison(comparisonId: string | null) {
  return useQuery({
    queryKey: ["analysis-compare", comparisonId] as const,
    queryFn: () => apiRequest<AnalysisCompareResponse>(`/api/analysis/compare/${comparisonId}`),
    enabled: Boolean(comparisonId),
    staleTime: 10_000,
    retry: 2,
  });
}
