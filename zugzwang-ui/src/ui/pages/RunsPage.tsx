import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { useRuns } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function RunsPage() {
  const [query, setQuery] = useState("");
  const [evaluatedOnly, setEvaluatedOnly] = useState(false);
  const runsQuery = useRuns({ q: query, evaluatedOnly });
  const runs = runsQuery.data ?? [];

  return (
    <section>
      <PageHeader
        eyebrow="Runs"
        title="Run Explorer"
        subtitle="Inspect run metadata, filter by text/evaluation status and open details/replay."
      />

      <div className="mb-4 grid gap-3 rounded-2xl border border-[#d9d1c4] bg-white/80 p-4 lg:grid-cols-[1fr_auto_auto]">
        <label className="text-xs text-[#4f6774]">
          Search run id
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="best_known_start..."
            className="mt-1 w-full rounded-lg border border-[#d9d2c6] bg-[#f8f5ee] px-2.5 py-2 text-sm text-[#2a4351]"
          />
        </label>

        <label className="inline-flex items-center gap-2 self-end pb-1 text-sm text-[#2a4351]">
          <input
            type="checkbox"
            checked={evaluatedOnly}
            onChange={(event) => setEvaluatedOnly(event.target.checked)}
            className="h-4 w-4 rounded border-[#c7c1b6]"
          />
          Evaluated only
        </label>

        <div className="flex items-end">
          <Link
            to="/runs/compare"
            className="inline-flex items-center rounded-lg border border-[#1e6079] bg-[#1e6079] px-3 py-2 text-sm font-semibold text-[#eef8fd]"
          >
            Open run comparison
          </Link>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-[#d9d1c4] bg-white/85 shadow-[0_10px_24px_rgba(16,32,41,0.08)]">
        <div className="grid min-w-[760px] grid-cols-[2.2fr_1fr_1.2fr_1fr_1fr] border-b border-[#e2ddd2] bg-[#f5f2ea] px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#5e7382]">
          <span>Run ID</span>
          <span>Created</span>
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
            className="grid min-w-[760px] grid-cols-[2.2fr_1fr_1.2fr_1fr_1fr] items-center border-b border-[#f0ece2] px-4 py-3 text-sm text-[#27404f]"
          >
            <Link
              to="/runs/$runId"
              params={{ runId: run.run_id }}
              className="truncate font-medium text-[#1d5d77] hover:underline"
            >
              {run.run_id}
            </Link>
            <span className="truncate text-xs text-[#5d7280]">{formatCreatedAt(run.created_at_utc)}</span>
            <span className="truncate text-xs text-[#5d7280]">{run.config_hash ?? "--"}</span>
            <span>{run.report_exists ? "yes" : "no"}</span>
            <span>{run.evaluated_report_exists ? "yes" : "no"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatCreatedAt(value: string | null | undefined): string {
  if (!value) {
    return "--";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}
