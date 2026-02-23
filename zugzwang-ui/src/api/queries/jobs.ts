import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "../client";
import type { CancelJobResponse, JobResponse, RunProgressResponse, StartEvalRequest, StartJobRequest } from "../types";

export const jobsQueryKey = ["jobs"] as const;
const JOB_POLL_INTERVAL_MS = 2_000;

export function useJobs() {
  return useQuery({
    queryKey: jobsQueryKey,
    queryFn: () => apiRequest<JobResponse[]>("/api/jobs"),
    // Keep jobs fresh even when all known jobs are terminal, so externally
    // started runs (CLI/API) become visible without manual refresh.
    refetchInterval: JOB_POLL_INTERVAL_MS,
  });
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId] as const,
    queryFn: () => apiRequest<JobResponse>(`/api/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => (shouldPollStatus(query.state.data?.status) ? JOB_POLL_INTERVAL_MS : false),
  });
}

export function useJobProgress(jobId: string | null) {
  return useQuery({
    queryKey: ["job-progress", jobId] as const,
    queryFn: () => apiRequest<RunProgressResponse>(`/api/jobs/${jobId}/progress`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => (shouldPollStatus(query.state.data?.status) ? JOB_POLL_INTERVAL_MS : false),
  });
}

export function useStartRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StartJobRequest) =>
      apiRequest<JobResponse>("/api/jobs/run", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (job) => {
      syncJobsAfterStart(queryClient, job);
    },
  });
}

export function useStartPlay() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StartJobRequest) =>
      apiRequest<JobResponse>("/api/jobs/play", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (job) => {
      syncJobsAfterStart(queryClient, job);
    },
  });
}

export function useStartEvaluation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StartEvalRequest) =>
      apiRequest<JobResponse>("/api/jobs/evaluate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (job) => {
      syncJobsAfterStart(queryClient, job);
    },
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

function syncJobsAfterStart(queryClient: QueryClient, job: JobResponse): void {
  queryClient.setQueryData<JobResponse[]>(jobsQueryKey, (current) => upsertJob(current ?? [], job));
  queryClient.setQueryData<JobResponse>(["job", job.job_id], job);
  queryClient.invalidateQueries({ queryKey: jobsQueryKey }).catch(() => undefined);
}

function upsertJob(current: JobResponse[], job: JobResponse): JobResponse[] {
  const next = current.filter((item) => item.job_id !== job.job_id);
  next.unshift(job);
  return next;
}

function shouldPollStatus(status: JobResponse["status"] | RunProgressResponse["status"] | null | undefined): boolean {
  if (!status) {
    return true;
  }
  return status === "queued" || status === "running";
}

