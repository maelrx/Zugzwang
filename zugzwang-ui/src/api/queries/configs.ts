import { useMutation, useQuery } from "@tanstack/react-query";
import { apiRequest } from "../client";
import type { ConfigListResponse } from "../types";

export const configsQueryKey = ["configs"] as const;

export function useConfigs() {
  return useQuery({
    queryKey: configsQueryKey,
    queryFn: () => apiRequest<ConfigListResponse>("/api/configs"),
    staleTime: 60_000,
  });
}

export function useValidateConfig() {
  return useMutation({
    mutationFn: (payload: { config_path: string; model_profile?: string | null; overrides?: string[] }) =>
      apiRequest("/api/configs/validate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function usePreviewConfig() {
  return useMutation({
    mutationFn: (payload: { config_path: string; model_profile?: string | null; overrides?: string[] }) =>
      apiRequest("/api/configs/preview", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

