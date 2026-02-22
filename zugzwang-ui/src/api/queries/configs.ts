import { useMutation, useQuery } from "@tanstack/react-query";
import { apiRequest } from "../client";
import type {
  ConfigListResponse,
  ConfigPreviewResponse,
  ConfigValidateRequest,
  ConfigValidateResponse,
  ModelProviderPresetResponse,
} from "../types";

export const configsQueryKey = ["configs"] as const;

export function useConfigs() {
  return useQuery({
    queryKey: configsQueryKey,
    queryFn: () => apiRequest<ConfigListResponse>("/api/configs"),
    staleTime: 60_000,
  });
}

export function useModelCatalog() {
  return useQuery({
    queryKey: ["model-catalog"] as const,
    queryFn: () => apiRequest<ModelProviderPresetResponse[]>("/api/configs/model-catalog"),
    staleTime: 60_000,
  });
}

export function useValidateConfig() {
  return useMutation({
    mutationFn: (payload: ConfigValidateRequest) =>
      apiRequest<ConfigValidateResponse>("/api/configs/validate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function usePreviewConfig() {
  return useMutation({
    mutationFn: (payload: ConfigValidateRequest) =>
      apiRequest<ConfigPreviewResponse>("/api/configs/preview", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}
