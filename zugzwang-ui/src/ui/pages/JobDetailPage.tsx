import { Link, useParams } from "@tanstack/react-router";
import { useJobLogs } from "../../api/logs";
import { useCancelJob, useJob, useJobProgress } from "../../api/queries";
import { LogTerminal } from "../components/LogTerminal";
import { PageHeader } from "../components/PageHeader";

export function JobDetailPage() {
  const params = useParams({ strict: false }) as { jobId: string };
  const jobId = params.jobId;

  const jobQuery = useJob(jobId);
  const progressQuery = useJobProgress(jobId);
  const cancelMutation = useCancelJob();
  const logs = useJobLogs(jobId);

  const job = jobQuery.data;
  const progress = progressQuery.data;

  const canCancel = job?.status === "running" || job?.status === "queued";

  return (
    <section>
      <PageHeader
        eyebrow="Job Detail"
        title={`Job ${jobId}`}
        subtitle="Live status and log stream from FastAPI + SSE."
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Status" value={job?.status ?? "--"} />
        <StatTile label="Type" value={job?.job_type ?? "--"} />
        <StatTile label="Run ID" value={job?.run_id ?? "--"} />
        <StatTile label="Games" value={progress ? `${progress.games_written}/${progress.games_target ?? "--"}` : "--"} />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        {canCancel && (
          <button
            type="button"
            className="rounded-lg border border-[#9f3a3a] bg-[#b94444] px-3 py-2 text-sm font-semibold text-white hover:bg-[#a43f3f]"
            onClick={() => cancelMutation.mutate(jobId)}
            disabled={cancelMutation.isPending}
          >
            {cancelMutation.isPending ? "Canceling..." : "Cancel job"}
          </button>
        )}

        {job?.run_id && (
          <Link
            to="/runs/$runId"
            params={{ runId: job.run_id }}
            className="rounded-lg border border-[#1e6079] bg-[#1e6079] px-3 py-2 text-sm font-semibold text-[#eef8fd]"
          >
            Open run detail
          </Link>
        )}

        <Link to="/dashboard/jobs" className="rounded-lg border border-[#d5cdc0] bg-white px-3 py-2 text-sm font-medium text-[#314a58]">
          Back to jobs
        </Link>
      </div>

      {(jobQuery.isLoading || progressQuery.isLoading) && (
        <p className="mb-3 text-sm text-[#516672]">Loading job and progress...</p>
      )}

      {(jobQuery.isError || progressQuery.isError || cancelMutation.isError || logs.error) && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff2f0] px-3 py-2 text-sm text-[#8a3434]">
          Failed to fetch one or more job details.
        </p>
      )}

      <LogTerminal lines={logs.lines} done={logs.done} />
    </section>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-xl border border-[#d9d2c6] bg-white/85 px-3 py-2">
      <p className="text-xs uppercase tracking-[0.14em] text-[#647987]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-[#1f3947]">{value}</p>
    </article>
  );
}
