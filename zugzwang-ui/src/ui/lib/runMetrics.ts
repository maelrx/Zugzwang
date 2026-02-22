import type { JobResponse, RunSummaryResponse } from "../../api/types";

type UnknownRecord = Record<string, unknown>;

export type RunMetrics = {
  targetGames: number | null;
  validGames: number | null;
  completionRate: number | null;
  totalCostUsd: number | null;
  acplOverall: number | null;
  blunderRate: number | null;
  bestMoveAgreement: number | null;
  eloMle: number | null;
  eloCiLower: number | null;
  eloCiUpper: number | null;
  stoppedDueToBudget: boolean | null;
  budgetStopReason: string | null;
};

export type DashboardKpis = {
  activeJobs: number;
  runsIndexed: number;
  evaluatedRuns: number;
  completionRate: number | null;
  totalSpendUsd: number;
  avgAcpl: number | null;
  budgetStops: number;
  lastRunId: string | null;
};

export function extractRunMetrics(summary: RunSummaryResponse | null | undefined): RunMetrics {
  const report = asRecord(summary?.report);
  const evaluatedRoot = asRecord(summary?.evaluated_report);
  const evaluatedMetrics = asRecord(evaluatedRoot.metrics);
  const evaluatedElo = asRecord(evaluatedRoot.elo_estimate);
  const reportElo = asRecord(report.elo_estimate);

  const targetGames = firstNumber(report.num_games_target, evaluatedRoot.num_games_target);
  const validGames = firstNumber(report.num_games_valid, evaluatedRoot.num_games_valid);

  const eloCiFromRoot = maybeNumberTuple(evaluatedRoot.elo_ci_95);
  const eloCiFromNested = maybeNumberTuple(evaluatedElo.elo_ci_95);

  return {
    targetGames,
    validGames,
    completionRate: firstNumber(report.completion_rate, evaluatedRoot.completion_rate),
    totalCostUsd: firstNumber(report.total_cost_usd, evaluatedRoot.total_cost_usd),
    acplOverall: firstNumber(evaluatedMetrics.acpl_overall, evaluatedRoot.acpl_overall, report.acpl_overall),
    blunderRate: firstNumber(evaluatedMetrics.blunder_rate, evaluatedRoot.blunder_rate, report.blunder_rate),
    bestMoveAgreement: firstNumber(
      evaluatedMetrics.best_move_agreement,
      evaluatedRoot.best_move_agreement,
      report.best_move_agreement,
    ),
    eloMle: firstNumber(
      evaluatedElo.elo_mle,
      evaluatedRoot.elo_estimate,
      reportElo.elo_mle,
      report.elo_estimate,
    ),
    eloCiLower: firstNumber(
      evaluatedElo.elo_ci_lower,
      eloCiFromNested[0],
      eloCiFromRoot[0],
      report.elo_ci_95_lower,
    ),
    eloCiUpper: firstNumber(
      evaluatedElo.elo_ci_upper,
      eloCiFromNested[1],
      eloCiFromRoot[1],
      report.elo_ci_95_upper,
    ),
    stoppedDueToBudget: firstBoolean(report.stopped_due_to_budget, evaluatedRoot.stopped_due_to_budget),
    budgetStopReason: firstString(report.budget_stop_reason, evaluatedRoot.budget_stop_reason),
  };
}

export function computeDashboardKpis(
  jobs: JobResponse[],
  runs: { run_id: string; evaluated_report_exists: boolean }[],
  summaries: RunSummaryResponse[],
): DashboardKpis {
  const metrics = summaries.map((summary) => extractRunMetrics(summary));
  const totalTargetGames = sumNumbers(metrics.map((item) => item.targetGames));
  const totalValidGames = sumNumbers(metrics.map((item) => item.validGames));
  const totalSpendUsd = sumNumbers(metrics.map((item) => item.totalCostUsd));

  const acplValues = metrics.map((item) => item.acplOverall).filter((value): value is number => typeof value === "number");
  const avgAcpl = acplValues.length > 0 ? acplValues.reduce((acc, value) => acc + value, 0) / acplValues.length : null;
  const completionRate = totalTargetGames > 0 ? totalValidGames / totalTargetGames : null;

  return {
    activeJobs: jobs.filter((job) => job.status === "running" || job.status === "queued").length,
    runsIndexed: runs.length,
    evaluatedRuns: runs.filter((run) => run.evaluated_report_exists).length,
    completionRate,
    totalSpendUsd,
    avgAcpl,
    budgetStops: metrics.filter((item) => item.stoppedDueToBudget === true).length,
    lastRunId: runs[0]?.run_id ?? null,
  };
}

export function formatInteger(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return String(Math.round(value));
}

export function formatRate(value: number | null | undefined, fractionDigits = 1): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${(value * 100).toFixed(fractionDigits)}%`;
}

export function formatDecimal(value: number | null | undefined, fractionDigits = 3): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(fractionDigits);
}

export function formatUsd(value: number | null | undefined, fractionDigits = 4): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(fractionDigits);
}

export function formatCi(lower: number | null | undefined, upper: number | null | undefined): string {
  if (typeof lower !== "number" || typeof upper !== "number" || Number.isNaN(lower) || Number.isNaN(upper)) {
    return "--";
  }
  return `[${lower.toFixed(1)}, ${upper.toFixed(1)}]`;
}

function sumNumbers(values: Array<number | null>): number {
  return values.reduce<number>((acc, value) => acc + (typeof value === "number" ? value : 0), 0);
}

function asRecord(value: unknown): UnknownRecord {
  if (value && typeof value === "object") {
    return value as UnknownRecord;
  }
  return {};
}

function firstNumber(...values: unknown[]): number | null {
  for (const value of values) {
    const numeric = toNumber(value);
    if (numeric !== null) {
      return numeric;
    }
  }
  return null;
}

function firstBoolean(...values: unknown[]): boolean | null {
  for (const value of values) {
    if (typeof value === "boolean") {
      return value;
    }
  }
  return null;
}

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
  }
  return null;
}

function maybeNumberTuple(value: unknown): [number | null, number | null] {
  if (!Array.isArray(value) || value.length < 2) {
    return [null, null];
  }
  return [toNumber(value[0]), toNumber(value[1])];
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}
