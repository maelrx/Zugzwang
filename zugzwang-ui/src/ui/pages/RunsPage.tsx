import { Link } from "@tanstack/react-router";
import { useRuns } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function RunsPage() {
  const runsQuery = useRuns();
  const runs = runsQuery.data ?? [];

  return (
    <section>
      <PageHeader
        eyebrow="Runs"
        title="Run Explorer"
        subtitle="This page already reads `/api/runs`. Next step is adding detail tabs, replay routes, and comparison UI."
      />

      <div className="mb-4">
        <Link
          to="/runs/compare"
          className="inline-flex items-center rounded-lg border border-[#1e6079] bg-[#1e6079] px-3 py-2 text-sm font-semibold text-[#eef8fd]"
        >
          Open run comparison
        </Link>
      </div>

      <div className="overflow-hidden rounded-2xl border border-[#d9d1c4] bg-white/85 shadow-[0_10px_24px_rgba(16,32,41,0.08)]">
        <div className="grid grid-cols-[2.2fr_1.2fr_1fr_1fr] border-b border-[#e2ddd2] bg-[#f5f2ea] px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#5e7382]">
          <span>Run ID</span>
          <span>Config hash</span>
          <span>Report</span>
          <span>Evaluated</span>
        </div>

        {runsQuery.isLoading && <p className="px-4 py-4 text-sm text-[#5d6f7a]">Loading runs from API...</p>}

        {runsQuery.isError && <p className="px-4 py-4 text-sm text-[#8a3131]">Failed to load runs.</p>}

        {!runsQuery.isLoading && !runsQuery.isError && runs.length === 0 && (
          <p className="px-4 py-4 text-sm text-[#5d6f7a]">No runs found in `results/runs`.</p>
        )}

        {runs.map((run) => (
          <div
            key={run.run_id}
            className="grid grid-cols-[2.2fr_1.2fr_1fr_1fr] items-center border-b border-[#f0ece2] px-4 py-3 text-sm text-[#27404f]"
          >
            <Link
              to="/runs/$runId"
              params={{ runId: run.run_id }}
              className="truncate font-medium text-[#1d5d77] hover:underline"
            >
              {run.run_id}
            </Link>
            <span className="truncate text-xs text-[#5d7280]">{run.config_hash ?? "--"}</span>
            <span>{run.report_exists ? "yes" : "no"}</span>
            <span>{run.evaluated_report_exists ? "yes" : "no"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
