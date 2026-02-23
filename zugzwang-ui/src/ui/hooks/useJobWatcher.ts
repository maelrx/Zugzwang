import { useEffect, useMemo, useRef } from "react";
import { useJobs } from "../../api/queries";
import { type JobResponse } from "../../api/types";
import { useNotificationStore } from "../../stores/notificationsStore";
import { usePreferencesStore } from "../../stores/preferencesStore";

const TERMINAL_STATUSES = new Set(["completed", "failed", "canceled"]);
const STARTED_STATUSES = new Set(["running"]);

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
        if (!changed) {
          continue;
        }
        if (STARTED_STATUSES.has(job.status) && previous === "queued") {
          pushToast(buildStartedToast(job));
          continue;
        }
        if (TERMINAL_STATUSES.has(job.status)) {
          pushToast(buildTerminalToast(job));
        }
      }
    }

    previousStatusesRef.current = nextStatuses;
  }, [jobs, notificationsEnabled, pushToast]);
}

function buildStartedToast(job: JobResponse) {
  return {
    title: "Job started",
    message: `${job.job_type} ${job.job_id} is now running.`,
    tone: "info" as const,
    linkTo: `/dashboard/jobs/${job.job_id}`,
    linkLabel: "Open job",
  };
}

function buildTerminalToast(job: JobResponse) {
  if (job.status === "completed" && job.job_type === "evaluate") {
    return {
      title: "Evaluation complete",
      message: `${job.run_id ?? job.job_id} evaluation finished.`,
      tone: "success" as const,
      linkTo: job.run_id ? `/runs/${job.run_id}?tab=overview` : `/dashboard/jobs/${job.job_id}`,
      linkLabel: job.run_id ? "Open run" : "Open job",
    };
  }
  if (job.status === "completed") {
    return {
      title: "Job completed",
      message: `${job.job_type} ${job.job_id} finished successfully.`,
      tone: "success" as const,
      linkTo: job.run_id ? `/runs/${job.run_id}` : `/dashboard/jobs/${job.job_id}`,
      linkLabel: job.run_id ? "Open run" : "Open job",
    };
  }
  if (job.status === "failed") {
    return {
      title: "Job failed",
      message: `${job.job_type} ${job.job_id} failed. Check logs for details.`,
      tone: "error" as const,
      linkTo: `/dashboard/jobs/${job.job_id}`,
      linkLabel: "Open logs",
    };
  }
  return {
    title: "Job canceled",
    message: `${job.job_type} ${job.job_id} was canceled.`,
    tone: "warning" as const,
    linkTo: `/dashboard/jobs/${job.job_id}`,
    linkLabel: "Open job",
  };
}
