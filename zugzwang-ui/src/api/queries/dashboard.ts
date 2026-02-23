import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../client";
import type { DashboardKpisResponse } from "../types";

export function useDashboardKpis(timelineLimit = 40) {
  const params = new URLSearchParams();
  params.set("timeline_limit", String(timelineLimit));
  const query = params.toString();
  const path = query ? `/api/dashboard/kpis?${query}` : "/api/dashboard/kpis";

  return useQuery({
    queryKey: ["dashboard", "kpis", timelineLimit] as const,
    queryFn: () => apiRequest<DashboardKpisResponse>(path),
    staleTime: 5_000,
  });
}
