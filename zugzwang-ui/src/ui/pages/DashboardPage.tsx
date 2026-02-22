import { useJobs, useRuns } from "../../api/queries";
import { InfoCard } from "../components/InfoCard";
import { PageHeader } from "../components/PageHeader";

export function DashboardPage() {
  const jobsQuery = useJobs();
  const runsQuery = useRuns();

  const jobs = jobsQuery.data ?? [];
  const runs = runsQuery.data ?? [];
  const activeJobs = jobs.filter((job) => job.status === "running" || job.status === "queued").length;
  const lastRun = runs[0]?.run_id ?? "--";

  return (
    <section>
      <PageHeader
        eyebrow="Home"
        title="Research Operations Dashboard"
        subtitle="Live data now comes from the FastAPI layer. Next milestones expand metrics and drill-down analytics."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <InfoCard title="Active jobs" value={String(activeJobs)} hint={jobsQuery.isLoading ? "Loading jobs..." : "Polled from /api/jobs"} />
        <InfoCard title="Runs indexed" value={String(runs.length)} hint={runsQuery.isLoading ? "Loading runs..." : "Loaded from /api/runs"} />
        <InfoCard title="Total spend" value="--" hint="Derived from experiment reports." />
        <InfoCard title="Last run" value={lastRun} hint="Sorted by latest run timestamp/id." />
      </div>

      {(jobsQuery.isError || runsQuery.isError) && (
        <div className="mt-5 rounded-xl border border-[#c58f8f] bg-[#fff3f1] px-4 py-3 text-sm text-[#7f2d2d]">
          Failed to load one or more dashboard widgets from API.
        </div>
      )}
    </section>
  );
}
