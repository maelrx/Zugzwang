import { useEffect, useMemo, useRef } from "react";
import { useJobs } from "../../api/queries";
import { type JobResponse } from "../../api/types";
import { useNotificationStore } from "../../stores/notificationsStore";
import { usePreferencesStore } from "../../stores/preferencesStore";

const TERMINAL_STATUSES = new Set(["completed", "failed", "canceled"]);

type JobsStatusMap = Map<string, string>;

export function useJobWatcher() {
  const jobsQuery = useJobs();
  const pushToast = useNotificationStore((state) => state.pushToast);
  const notificationsEnabled = usePreferencesStore((state) => state.notificationsEnabled);
  const previousStatusesRef = useRef<JobsStatusMap | null>(null);

  const jobs = useMemo(() => jobsQuery.data ?? [], [jobsQuery.data]);

  useEffect(() => {
    if (!notificationsEnabled || jobs.length === 0) {
      if (jobs.length === 0) {
        previousStatusesRef.current = null;
      }
      return;
    }

    const nextStatuses = new Map(jobs.map((job) => [job.job_id, job.status]));
    const previousStatuses = previousStatusesRef.current;

    if (previousStatuses) {
      for (const job of jobs) {
        const previous = previousStatuses.get(job.job_id);
        const changed = previous !== undefined && previous !== job.status;
        if (!changed || !TERMINAL_STATUSES.has(job.status)) {
          continue;
        }

        pushToast(buildStatusToast(job));
      }
    }

    previousStatusesRef.current = nextStatuses;
  }, [jobs, notificationsEnabled, pushToast]);
}

function buildStatusToast(job: JobResponse) {
  if (job.status === "completed") {
    return {
      title: "Job completed",
      message: `${job.job_type} ${job.job_id} finished successfully.`,
      tone: "success" as const,
    };
  }
  if (job.status === "failed") {
    return {
      title: "Job failed",
      message: `${job.job_type} ${job.job_id} failed. Check logs for details.`,
      tone: "error" as const,
    };
  }
  return {
    title: "Job canceled",
    message: `${job.job_type} ${job.job_id} was canceled.`,
    tone: "warning" as const,
  };
}

