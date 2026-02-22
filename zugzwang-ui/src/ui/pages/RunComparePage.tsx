import { useMemo, useState } from "react";
import { useRunSummary, useRuns } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";
import { extractRunMetrics, formatDecimal, formatInteger, formatRate, formatUsd } from "../lib/runMetrics";

export function RunComparePage() {
  const runsQuery = useRuns();
  const runs = runsQuery.data ?? [];
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");

  const summaryA = useRunSummary(runA || null);
  const summaryB = useRunSummary(runB || null);

  const metricsA = useMemo(() => extractRunMetrics(summaryA.data), [summaryA.data]);
  const metricsB = useMemo(() => extractRunMetrics(summaryB.data), [summaryB.data]);

  const rows = useMemo(
    () => [
      buildRow("Target games", formatInteger(metricsA.targetGames), formatInteger(metricsB.targetGames), null),
      buildRow("Valid games", formatInteger(metricsA.validGames), formatInteger(metricsB.validGames), null),
      buildRow(
        "Completion rate",
        formatRate(metricsA.completionRate),
        formatRate(metricsB.completionRate),
        compareHigherIsBetter(metricsA.completionRate, metricsB.completionRate, "completion"),
      ),
      buildRow(
        "Total cost USD",
        formatUsd(metricsA.totalCostUsd),
        formatUsd(metricsB.totalCostUsd),
        compareLowerIsBetter(metricsA.totalCostUsd, metricsB.totalCostUsd, "cost"),
      ),
      buildRow(
        "ACPL",
        formatDecimal(metricsA.acplOverall, 1),
        formatDecimal(metricsB.acplOverall, 1),
        compareLowerIsBetter(metricsA.acplOverall, metricsB.acplOverall, "ACPL"),
      ),
      buildRow(
        "Blunder rate",
        formatRate(metricsA.blunderRate),
        formatRate(metricsB.blunderRate),
        compareLowerIsBetter(metricsA.blunderRate, metricsB.blunderRate, "blunder"),
      ),
      buildRow(
        "Best move agreement",
        formatRate(metricsA.bestMoveAgreement),
        formatRate(metricsB.bestMoveAgreement),
        compareHigherIsBetter(metricsA.bestMoveAgreement, metricsB.bestMoveAgreement, "agreement"),
      ),
      buildRow(
        "Elo MLE",
        formatDecimal(metricsA.eloMle, 1),
        formatDecimal(metricsB.eloMle, 1),
        compareHigherIsBetter(metricsA.eloMle, metricsB.eloMle, "Elo"),
      ),
    ],
    [
      metricsA.acplOverall,
      metricsA.bestMoveAgreement,
      metricsA.blunderRate,
      metricsA.completionRate,
      metricsA.eloMle,
      metricsA.targetGames,
      metricsA.totalCostUsd,
      metricsA.validGames,
      metricsB.acplOverall,
      metricsB.bestMoveAgreement,
      metricsB.blunderRate,
      metricsB.completionRate,
      metricsB.eloMle,
      metricsB.targetGames,
      metricsB.totalCostUsd,
      metricsB.validGames,
    ],
  );

  const bothRunsSelected = runA.length > 0 && runB.length > 0;
  const comparingSameRun = bothRunsSelected && runA === runB;

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

      {!bothRunsSelected && (
        <p className="mb-3 rounded-lg border border-[#cfd7dc] bg-[#f3f7fa] px-3 py-2 text-sm text-[#48616f]">
          Select two runs to populate comparison metrics.
        </p>
      )}

      {comparingSameRun && (
        <p className="mb-3 rounded-lg border border-[#d7b071] bg-[#fff3de] px-3 py-2 text-sm text-[#7d5618]">
          You selected the same run on both sides, so no meaningful delta can be computed.
        </p>
      )}

      {(summaryA.isError || summaryB.isError) && bothRunsSelected && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff2ef] px-3 py-2 text-sm text-[#8a3434]">
          Failed to load one or both run summaries.
        </p>
      )}

      <div className="overflow-hidden rounded-2xl border border-[#d9d1c4] bg-white/85">
        <div className="grid grid-cols-[1.4fr_1fr_1fr_1.2fr] border-b border-[#e6dfd3] bg-[#f4f1ea] px-4 py-2 text-xs uppercase tracking-[0.14em] text-[#627786]">
          <span>Metric</span>
          <span className="truncate">{runA || "Run A"}</span>
          <span className="truncate">{runB || "Run B"}</span>
          <span>Delta</span>
        </div>
        {rows.map((row) => (
          <CompareRow
            key={row.label}
            label={row.label}
            left={row.left}
            right={row.right}
            delta={row.delta?.text ?? "--"}
            tone={row.delta?.tone ?? "neutral"}
          />
        ))}
      </div>
    </section>
  );
}

type DeltaTone = "good" | "bad" | "neutral";

function CompareRow({ label, left, right, delta, tone }: { label: string; left: string; right: string; delta: string; tone: DeltaTone }) {
  return (
    <div className="grid grid-cols-[1.4fr_1fr_1fr_1.2fr] border-b border-[#f0ebe3] px-4 py-3 text-sm text-[#2a4350]">
      <span>{label}</span>
      <span>{left}</span>
      <span>{right}</span>
      <span className={deltaClassName(tone)}>{delta}</span>
    </div>
  );
}

function buildRow(label: string, left: string, right: string, delta: { text: string; tone: DeltaTone } | null) {
  return { label, left, right, delta };
}

function compareHigherIsBetter(a: number | null, b: number | null, metricName: string): { text: string; tone: DeltaTone } | null {
  if (!isFiniteNumber(a) || !isFiniteNumber(b)) {
    return null;
  }
  const delta = a - b;
  if (Math.abs(delta) < 1e-6) {
    return { text: `tie ${metricName}`, tone: "neutral" };
  }
  const winner = delta > 0 ? "A" : "B";
  return {
    text: `${winner} better by ${Math.abs(delta).toFixed(3)}`,
    tone: delta > 0 ? "good" : "bad",
  };
}

function compareLowerIsBetter(a: number | null, b: number | null, metricName: string): { text: string; tone: DeltaTone } | null {
  if (!isFiniteNumber(a) || !isFiniteNumber(b)) {
    return null;
  }
  const delta = b - a;
  if (Math.abs(delta) < 1e-6) {
    return { text: `tie ${metricName}`, tone: "neutral" };
  }
  const winner = delta > 0 ? "A" : "B";
  return {
    text: `${winner} better by ${Math.abs(delta).toFixed(3)}`,
    tone: delta > 0 ? "good" : "bad",
  };
}

function isFiniteNumber(value: number | null): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function deltaClassName(tone: DeltaTone): string {
  if (tone === "good") {
    return "font-semibold text-[#1f6a49]";
  }
  if (tone === "bad") {
    return "font-semibold text-[#8d3131]";
  }
  return "text-[#5c7280]";
}
