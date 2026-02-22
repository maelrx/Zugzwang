import { Link } from "@tanstack/react-router";
import { useJobs } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function JobsPage() {
  const jobsQuery = useJobs();
  const jobs = jobsQuery.data ?? [];

  return (
    <section>
      <PageHeader
        eyebrow="Jobs"
        title="Execution Monitor"
        subtitle="Real-time job status and SSE logs will be rendered here from /api/jobs and /api/jobs/{id}/logs."
      />

      <div className="overflow-hidden rounded-2xl border border-[#d6d0c5] bg-white/85">
        <div className="grid grid-cols-[1.6fr_1fr_1fr_1.4fr] border-b border-[#e5dfd4] bg-[#f4f1ea] px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#607786]">
          <span>Job ID</span>
          <span>Type</span>
          <span>Status</span>
          <span>Run ID</span>
        </div>

        {jobsQuery.isLoading && <p className="px-4 py-4 text-sm text-[#4f6774]">Loading jobs...</p>}
        {jobsQuery.isError && <p className="px-4 py-4 text-sm text-[#8a3434]">Failed to load jobs.</p>}
        {!jobsQuery.isLoading && !jobsQuery.isError && jobs.length === 0 && (
          <p className="px-4 py-4 text-sm text-[#4f6774]">No jobs tracked yet.</p>
        )}

        {jobs.map((job) => (
          <div
            key={job.job_id}
            className="grid grid-cols-[1.6fr_1fr_1fr_1.4fr] items-center border-b border-[#f0ece3] px-4 py-3 text-sm text-[#28404f]"
          >
            <Link to="/jobs/$jobId" params={{ jobId: job.job_id }} className="truncate font-medium text-[#1d5d77] hover:underline">
              {job.job_id}
            </Link>
            <span>{job.job_type}</span>
            <span>{job.status}</span>
            <span className="truncate text-xs text-[#5c7280]">{job.run_id ?? "--"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
