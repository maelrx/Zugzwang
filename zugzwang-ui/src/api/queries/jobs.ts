import { useMutation, useQuery } from "@tanstack/react-query";
import { apiRequest } from "../client";
import type { CancelJobResponse, JobResponse, RunProgressResponse, StartEvalRequest, StartJobRequest } from "../types";

export const jobsQueryKey = ["jobs"] as const;

export function useJobs() {
  return useQuery({
    queryKey: jobsQueryKey,
    queryFn: () => apiRequest<JobResponse[]>("/api/jobs"),
    refetchInterval: (query) => {
      const jobs = query.state.data;
      if (!jobs?.length) {
        return false;
      }
      return jobs.some((job) => job.status === "running" || job.status === "queued") ? 2_000 : false;
    },
  });
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId] as const,
    queryFn: () => apiRequest<JobResponse>(`/api/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: 2_000,
  });
}

export function useJobProgress(jobId: string | null) {
  return useQuery({
    queryKey: ["job-progress", jobId] as const,
    queryFn: () => apiRequest<RunProgressResponse>(`/api/jobs/${jobId}/progress`),
    enabled: Boolean(jobId),
    refetchInterval: 2_000,
  });
}

export function useStartRun() {
  return useMutation({
    mutationFn: (payload: StartJobRequest) =>
      apiRequest<JobResponse>("/api/jobs/run", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useStartPlay() {
  return useMutation({
    mutationFn: (payload: StartJobRequest) =>
      apiRequest<JobResponse>("/api/jobs/play", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useStartEvaluation() {
  return useMutation({
    mutationFn: (payload: StartEvalRequest) =>
      apiRequest<JobResponse>("/api/jobs/evaluate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useCancelJob() {
  return useMutation({
    mutationFn: (jobId: string) =>
      apiRequest<CancelJobResponse>(`/api/jobs/${jobId}`, {
        method: "DELETE",
      }),
  });
}

