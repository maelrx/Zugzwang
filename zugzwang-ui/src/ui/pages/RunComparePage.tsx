import { useQueries } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiRequest } from "../../api/client";
import { useRunGames, useRunSummary, useRuns } from "../../api/queries";
import type { GameDetailResponse } from "../../api/types";
import { MoveQualityDistributionCompareCard } from "../components/MoveQualityDistributionCompareCard";
import { PhaseMetricCompareCard } from "../components/PhaseMetricCompareCard";
import { PageHeader } from "../components/PageHeader";
import { aggregateMoveQuality } from "../lib/moveQuality";
import { extractRunMetrics, formatDecimal, formatInteger, formatRate, formatUsd } from "../lib/runMetrics";

const MAX_QUALITY_GAMES_SAMPLE = 20;

export function RunComparePage() {
  const runsQuery = useRuns();
  const runs = runsQuery.data ?? [];
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");

  const summaryA = useRunSummary(runA || null);
  const summaryB = useRunSummary(runB || null);
  const runAGamesQuery = useRunGames(runA || null);
  const runBGamesQuery = useRunGames(runB || null);

  const metricsA = useMemo(() => extractRunMetrics(summaryA.data), [summaryA.data]);
  const metricsB = useMemo(() => extractRunMetrics(summaryB.data), [summaryB.data]);
  const runAGames = useMemo(() => (runAGamesQuery.data ?? []).slice(0, MAX_QUALITY_GAMES_SAMPLE), [runAGamesQuery.data]);
  const runBGames = useMemo(() => (runBGamesQuery.data ?? []).slice(0, MAX_QUALITY_GAMES_SAMPLE), [runBGamesQuery.data]);

  const runADetailQueries = useQueries({
    queries: runAGames.map((game) => ({
      queryKey: ["run-compare-game-detail", runA, game.game_number] as const,
      queryFn: () => apiRequest<GameDetailResponse>(`/api/runs/${runA}/games/${game.game_number}`),
      enabled: runA.length > 0,
      staleTime: Infinity,
    })),
  });

  const runBDetailQueries = useQueries({
    queries: runBGames.map((game) => ({
      queryKey: ["run-compare-game-detail", runB, game.game_number] as const,
      queryFn: () => apiRequest<GameDetailResponse>(`/api/runs/${runB}/games/${game.game_number}`),
      enabled: runB.length > 0,
      staleTime: Infinity,
    })),
  });

  const runADetails = useMemo(
    () => runADetailQueries.map((query) => query.data).filter((item): item is GameDetailResponse => Boolean(item)),
    [runADetailQueries],
  );
  const runBDetails = useMemo(
    () => runBDetailQueries.map((query) => query.data).filter((item): item is GameDetailResponse => Boolean(item)),
    [runBDetailQueries],
  );

  const qualityA = useMemo(() => aggregateMoveQuality(runADetails), [runADetails]);
  const qualityB = useMemo(() => aggregateMoveQuality(runBDetails), [runBDetails]);
  const qualityLoading =
    runAGamesQuery.isLoading ||
    runBGamesQuery.isLoading ||
    runADetailQueries.some((query) => query.isLoading) ||
    runBDetailQueries.some((query) => query.isLoading);
  const qualityError =
    runAGamesQuery.isError ||
    runBGamesQuery.isError ||
    runADetailQueries.some((query) => query.isError) ||
    runBDetailQueries.some((query) => query.isError);

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

      {qualityError && bothRunsSelected && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff2ef] px-3 py-2 text-sm text-[#8a3434]">
          Failed to load game details for move-quality comparison.
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

      {bothRunsSelected && (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <PhaseMetricCompareCard
            title="ACPL by phase"
            description="Lower is better. Bars are normalized to the max value across both runs."
            leftLabel="Run A"
            rightLabel="Run B"
            leftValues={metricsA.acplByPhase}
            rightValues={metricsB.acplByPhase}
            format="decimal"
            lowerIsBetter
          />
          <PhaseMetricCompareCard
            title="Retrieval hit-rate by phase"
            description="Higher is better. Shows retrieval coverage during opening/middlegame/endgame."
            leftLabel="Run A"
            rightLabel="Run B"
            leftValues={metricsA.retrievalHitRateByPhase}
            rightValues={metricsB.retrievalHitRateByPhase}
            format="percent"
          />
          <MoveQualityDistributionCompareCard
            title="Move-quality distribution"
            description={`Computed from sampled game moves (up to ${MAX_QUALITY_GAMES_SAMPLE} games per run).`}
            leftLabel="Run A"
            rightLabel="Run B"
            leftCounts={qualityA}
            rightCounts={qualityB}
          />
        </div>
      )}

      {qualityLoading && bothRunsSelected && (
        <p className="mt-3 rounded-lg border border-[#cfd7dc] bg-[#f3f7fa] px-3 py-2 text-sm text-[#48616f]">
          Loading move-quality distribution from sampled games...
        </p>
      )}
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
