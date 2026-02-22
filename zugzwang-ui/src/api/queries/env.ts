import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../client";
import type { EnvCheckResponse } from "../types";

export const envCheckQueryKey = ["env-check"] as const;

export function useEnvCheck() {
  return useQuery({
    queryKey: envCheckQueryKey,
    queryFn: () => apiRequest<EnvCheckResponse[]>("/api/env-check"),
    staleTime: 30_000,
  });
}

