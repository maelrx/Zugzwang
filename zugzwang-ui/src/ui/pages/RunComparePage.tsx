import { useMemo, useState } from "react";
import { useRunSummary, useRuns } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function RunComparePage() {
  const runsQuery = useRuns();
  const runs = runsQuery.data ?? [];
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");

  const summaryA = useRunSummary(runA || null);
  const summaryB = useRunSummary(runB || null);

  const metricsA = useMemo(() => extractMetrics(summaryA.data), [summaryA.data]);
  const metricsB = useMemo(() => extractMetrics(summaryB.data), [summaryB.data]);

  return (
    <section>
      <PageHeader
        eyebrow="Compare"
        title="Run Comparison"
        subtitle="Side-by-side comparison for core experiment and evaluation metrics."
      />

      <div className="mb-4 grid gap-3 lg:grid-cols-2">
        <label className="rounded-xl border border-[#d9d1c4] bg-white/85 p-3">
          <p className="mb-2 text-xs uppercase tracking-[0.14em] text-[#637886]">Run A</p>
          <select
            value={runA}
            onChange={(event) => setRunA(event.target.value)}
            className="w-full rounded-lg border border-[#d9d2c6] bg-[#f8f5ee] px-2.5 py-2 text-sm text-[#2a4351]"
          >
            <option value="">Select a run...</option>
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id}
              </option>
            ))}
          </select>
        </label>

        <label className="rounded-xl border border-[#d9d1c4] bg-white/85 p-3">
          <p className="mb-2 text-xs uppercase tracking-[0.14em] text-[#637886]">Run B</p>
          <select
            value={runB}
            onChange={(event) => setRunB(event.target.value)}
            className="w-full rounded-lg border border-[#d9d2c6] bg-[#f8f5ee] px-2.5 py-2 text-sm text-[#2a4351]"
          >
            <option value="">Select a run...</option>
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id}
              </option>
            ))}
          </select>
        </label>
      </div>

      {runsQuery.isLoading && <p className="mb-3 text-sm text-[#516672]">Loading runs...</p>}
      {runsQuery.isError && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff2ef] px-3 py-2 text-sm text-[#8a3434]">
          Failed to load runs list.
        </p>
      )}

      <div className="overflow-hidden rounded-2xl border border-[#d9d1c4] bg-white/85">
        <div className="grid grid-cols-[1.4fr_1fr_1fr] border-b border-[#e6dfd3] bg-[#f4f1ea] px-4 py-2 text-xs uppercase tracking-[0.14em] text-[#627786]">
          <span>Metric</span>
          <span className="truncate">{runA || "Run A"}</span>
          <span className="truncate">{runB || "Run B"}</span>
        </div>
        <CompareRow label="Target games" left={metricsA.targetGames} right={metricsB.targetGames} />
        <CompareRow label="Valid games" left={metricsA.validGames} right={metricsB.validGames} />
        <CompareRow label="Completion rate" left={metricsA.completionRate} right={metricsB.completionRate} />
        <CompareRow label="Total cost USD" left={metricsA.totalCost} right={metricsB.totalCost} />
        <CompareRow label="ACPL" left={metricsA.acpl} right={metricsB.acpl} />
        <CompareRow label="Blunder rate" left={metricsA.blunderRate} right={metricsB.blunderRate} />
        <CompareRow label="Elo MLE" left={metricsA.elo} right={metricsB.elo} />
      </div>
    </section>
  );
}

function CompareRow({ label, left, right }: { label: string; left: string; right: string }) {
  return (
    <div className="grid grid-cols-[1.4fr_1fr_1fr] border-b border-[#f0ebe3] px-4 py-3 text-sm text-[#2a4350]">
      <span>{label}</span>
      <span>{left}</span>
      <span>{right}</span>
    </div>
  );
}

type MetricSet = {
  targetGames: string;
  validGames: string;
  completionRate: string;
  totalCost: string;
  acpl: string;
  blunderRate: string;
  elo: string;
};

function extractMetrics(summary: unknown): MetricSet {
  const root = asRecord(summary);
  const report = asRecord(root.report);
  const evaluated = asRecord(root.evaluated_report);
  const evaluatedMetrics = asRecord(evaluated.metrics);
  const eloEstimate = asRecord(evaluated.elo_estimate);

  return {
    targetGames: asText(report.num_games_target),
    validGames: asText(report.num_games_valid),
    completionRate: asPercent(report.completion_rate),
    totalCost: asCost(report.total_cost_usd),
    acpl: asText(evaluatedMetrics.acpl_overall),
    blunderRate: asPercent(evaluatedMetrics.blunder_rate),
    elo: asText(eloEstimate.elo_mle),
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  return {};
}

function asText(value: unknown): string {
  if (value === null || value === undefined) {
    return "--";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  return String(value);
}

function asCost(value: unknown): string {
  if (typeof value !== "number") {
    return "--";
  }
  return value.toFixed(4);
}

function asPercent(value: unknown): string {
  if (typeof value !== "number") {
    return "--";
  }
  return `${(value * 100).toFixed(1)}%`;
}

