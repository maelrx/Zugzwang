import { useQueries } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../../api/client";
import { useRuns } from "../../api/queries";
import type { GameDetailResponse, GameListItem, RunSummaryResponse } from "../../api/types";
import { useCompareStore } from "../../stores/compareStore";
import { PageHeader } from "../components/PageHeader";
import { aggregateMoveQuality, type MoveQualityCounts } from "../lib/moveQuality";
import { extractRunMetrics, type PhaseKey, formatDecimal, formatRate, formatUsd } from "../lib/runMetrics";

const MAX_SELECTED_RUNS = 6;
const MAX_CHART_RUNS = 3;
const MAX_QUALITY_GAMES_SAMPLE = 10;
const QUALITY_KEYS = ["clean", "recovered", "illegal", "parseFail"] as const;
const PHASE_KEYS: PhaseKey[] = ["opening", "middlegame", "endgame"];

type DeltaTone = "good" | "bad" | "neutral";
type MetricDirection = "higher" | "lower" | "neutral";

type RowValue = {
  text: string;
  raw: number | null;
};

type MetricRow = {
  key: string;
  label: string;
  direction: MetricDirection;
  valuesByRun: Record<string, RowValue>;
};

export function RunComparePage() {
  const runsQuery = useRuns();
  const runs = runsQuery.data ?? [];

  const storeSelectedRunIds = useCompareStore((state) => state.selectedRunIds);
  const setStoreSelection = useCompareStore((state) => state.setSelection);

  const [searchText, setSearchText] = useState("");
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>(() => {
    const fromUrl = readRunIdsFromUrl(window.location.search);
    if (fromUrl.length > 0) {
      return fromUrl;
    }
    return storeSelectedRunIds.slice(0, MAX_SELECTED_RUNS);
  });
  const [visibleRunIds, setVisibleRunIds] = useState<string[]>([]);

  useEffect(() => {
    if (selectedRunIds.length > 0) {
      return;
    }
    if (storeSelectedRunIds.length > 0) {
      setSelectedRunIds(storeSelectedRunIds.slice(0, MAX_SELECTED_RUNS));
    }
  }, [selectedRunIds.length, storeSelectedRunIds]);

  useEffect(() => {
    if (!runsQuery.data) {
      return;
    }
    const validRunIds = new Set(runsQuery.data.map((run) => run.run_id));
    setSelectedRunIds((prev) => {
      const next = prev.filter((runId) => validRunIds.size === 0 || validRunIds.has(runId));
      return arraysEqual(prev, next) ? prev : next;
    });
  }, [runsQuery.data]);

  useEffect(() => {
    setStoreSelection(selectedRunIds);
    const params = new URLSearchParams(window.location.search);
    if (selectedRunIds.length > 0) {
      params.set("runs", selectedRunIds.join(","));
    } else {
      params.delete("runs");
    }
    const next = params.toString();
    const nextUrl = next.length > 0 ? `${window.location.pathname}?${next}` : window.location.pathname;
    window.history.replaceState(null, "", nextUrl);
  }, [selectedRunIds, setStoreSelection]);

  useEffect(() => {
    setVisibleRunIds((prev) => {
      const filtered = prev.filter((runId) => selectedRunIds.includes(runId));
      if (filtered.length > 0) {
        return filtered;
      }
      return selectedRunIds.slice(0, MAX_CHART_RUNS);
    });
  }, [selectedRunIds]);

  const selectedRunSet = useMemo(() => new Set(selectedRunIds), [selectedRunIds]);

  const filteredRuns = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    const candidates = runs.filter((run) => !selectedRunSet.has(run.run_id));
    if (!query) {
      return candidates.slice(0, 25);
    }
    return candidates
      .filter((run) => {
        const haystack = [run.run_id, run.inferred_model_label ?? "", run.inferred_provider ?? ""].join(" ").toLowerCase();
        return haystack.includes(query);
      })
      .slice(0, 25);
  }, [runs, searchText, selectedRunSet]);
  const emptySearchMessage = useMemo(() => {
    if (runsQuery.isLoading || filteredRuns.length > 0) {
      return null;
    }
    if (selectedRunIds.length >= MAX_SELECTED_RUNS) {
      return `Selection limit reached (${MAX_SELECTED_RUNS}). Remove one run to add another.`;
    }
    if (runs.length === 0) {
      return "No runs available yet.";
    }
    if (selectedRunIds.length > 0 && searchText.trim().length === 0) {
      return "All available runs are already selected.";
    }
    if (selectedRunIds.length > 0) {
      return "No additional runs match this search.";
    }
    return "No runs match this search.";
  }, [filteredRuns.length, runs.length, runsQuery.isLoading, searchText, selectedRunIds.length]);

  const summaryQueries = useQueries({
    queries: selectedRunIds.map((runId) => ({
      queryKey: ["run-compare-summary", runId] as const,
      queryFn: () => apiRequest<RunSummaryResponse>(`/api/runs/${runId}`),
      enabled: runId.length > 0,
      staleTime: 30_000,
      retry: 2,
    })),
  });

  const summaryByRun = useMemo(() => {
    const map = new Map<string, RunSummaryResponse>();
    for (let i = 0; i < selectedRunIds.length; i += 1) {
      const runId = selectedRunIds[i];
      const summary = summaryQueries[i]?.data;
      if (summary) {
        map.set(runId, summary);
      }
    }
    return map;
  }, [selectedRunIds, summaryQueries]);

  const metricsByRun = useMemo(() => {
    const map = new Map<string, ReturnType<typeof extractRunMetrics>>();
    for (const runId of selectedRunIds) {
      map.set(runId, extractRunMetrics(summaryByRun.get(runId)));
    }
    return map;
  }, [selectedRunIds, summaryByRun]);

  const chartRunIds = useMemo(() => selectedRunIds.slice(0, MAX_CHART_RUNS), [selectedRunIds]);

  const gamesQueries = useQueries({
    queries: chartRunIds.map((runId) => ({
      queryKey: ["run-compare-games", runId] as const,
      queryFn: () => apiRequest<GameListItem[]>(`/api/runs/${runId}/games`),
      enabled: runId.length > 0,
      staleTime: 60_000,
      retry: 2,
    })),
  });

  const sampledGamesByRun = useMemo(() => {
    const map = new Map<string, GameListItem[]>();
    for (let i = 0; i < chartRunIds.length; i += 1) {
      const runId = chartRunIds[i];
      const games = gamesQueries[i]?.data ?? [];
      map.set(runId, games.slice(0, MAX_QUALITY_GAMES_SAMPLE));
    }
    return map;
  }, [chartRunIds, gamesQueries]);

  const detailQuerySpecs = useMemo(
    () =>
      chartRunIds.flatMap((runId) =>
        (sampledGamesByRun.get(runId) ?? []).map((game) => ({
          runId,
          gameNumber: game.game_number,
        })),
      ),
    [chartRunIds, sampledGamesByRun],
  );

  const detailQueries = useQueries({
    queries: detailQuerySpecs.map((spec) => ({
      queryKey: ["run-compare-game-detail", spec.runId, spec.gameNumber] as const,
      queryFn: () => apiRequest<GameDetailResponse>(`/api/runs/${spec.runId}/games/${spec.gameNumber}`),
      enabled: spec.runId.length > 0,
      staleTime: Infinity,
      retry: 2,
    })),
  });

  const qualityByRun = useMemo(() => {
    const detailsMap = new Map<string, GameDetailResponse[]>();
    for (const runId of chartRunIds) {
      detailsMap.set(runId, []);
    }
    for (let i = 0; i < detailQuerySpecs.length; i += 1) {
      const spec = detailQuerySpecs[i];
      const detail = detailQueries[i]?.data;
      if (!detail) {
        continue;
      }
      const bucket = detailsMap.get(spec.runId) ?? [];
      bucket.push(detail);
      detailsMap.set(spec.runId, bucket);
    }

    const countsMap = new Map<string, MoveQualityCounts>();
    for (const runId of chartRunIds) {
      countsMap.set(runId, aggregateMoveQuality(detailsMap.get(runId) ?? []));
    }
    return countsMap;
  }, [chartRunIds, detailQueries, detailQuerySpecs]);

  const metricRows = useMemo(() => buildMetricRows(selectedRunIds, metricsByRun), [metricsByRun, selectedRunIds]);
  const deltaPairs = useMemo(() => buildDeltaPairs(selectedRunIds), [selectedRunIds]);

  const configDiff = useMemo(() => {
    if (selectedRunIds.length < 2) {
      return { compared: null as [string, string] | null, differences: [] as Array<{ key: string; left: string; right: string }> };
    }
    const leftRunId = selectedRunIds[0];
    const rightRunId = selectedRunIds[1];
    const leftResolved = summaryByRun.get(leftRunId)?.resolved_config;
    const rightResolved = summaryByRun.get(rightRunId)?.resolved_config;
    const leftFlat = flattenObject(leftResolved);
    const rightFlat = flattenObject(rightResolved);
    const keys = [...new Set([...Object.keys(leftFlat), ...Object.keys(rightFlat)])].sort((a, b) => a.localeCompare(b));
    const differences: Array<{ key: string; left: string; right: string }> = [];

    for (const key of keys) {
      if (key === "runtime.seed") {
        continue;
      }
      const leftValue = key in leftFlat ? stableStringify(leftFlat[key]) : "--";
      const rightValue = key in rightFlat ? stableStringify(rightFlat[key]) : "--";
      if (leftValue !== rightValue) {
        differences.push({ key, left: leftValue, right: rightValue });
      }
    }

    return {
      compared: [leftRunId, rightRunId] as [string, string],
      differences,
    };
  }, [selectedRunIds, summaryByRun]);

  const summaryError = summaryQueries.some((query) => query.isError);
  const qualityLoading = gamesQueries.some((query) => query.isLoading) || detailQueries.some((query) => query.isLoading);
  const qualityError = gamesQueries.some((query) => query.isError) || detailQueries.some((query) => query.isError);

  return (
    <section>
      <PageHeader
        eyebrow="Compare"
        title="Compare Workbench"
        subtitle="Multi-run side-by-side comparison with directional deltas, config diff and overlaid quality/phase charts."
      />

      <section className="mb-4 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <label className="text-xs text-[var(--color-text-secondary)]">
            Search runs to add
            <input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="run id / model / provider"
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            />
          </label>

          <button
            type="button"
            className="self-end rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
            onClick={() => {
              setSelectedRunIds([]);
              setSearchText("");
            }}
          >
            Clear selection
          </button>
        </div>

        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {filteredRuns.map((run) => (
            <button
              key={run.run_id}
              type="button"
              onClick={() =>
                setSelectedRunIds((prev) => {
                  if (prev.includes(run.run_id) || prev.length >= MAX_SELECTED_RUNS) {
                    return prev;
                  }
                  return [...prev, run.run_id];
                })
              }
              disabled={selectedRunIds.length >= MAX_SELECTED_RUNS}
              className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2 text-left text-sm text-[var(--color-text-primary)]"
            >
              <p className="truncate font-semibold">{run.run_id}</p>
              <p className="truncate text-xs text-[var(--color-text-secondary)]">
                {run.inferred_model_label ?? run.inferred_model ?? "--"} | {run.inferred_provider ?? "--"}
              </p>
            </button>
          ))}
        </div>

        {emptySearchMessage ? <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{emptySearchMessage}</p> : null}

        <div className="mt-3 flex flex-wrap gap-2">
          {selectedRunIds.map((runId) => (
            <button
              key={runId}
              type="button"
              onClick={() => setSelectedRunIds((prev) => prev.filter((id) => id !== runId))}
              className="rounded-full border border-[var(--color-primary-700)] bg-[var(--color-primary-50)] px-3 py-1 text-xs font-semibold text-[var(--color-primary-800)]"
            >
              {runId} x
            </button>
          ))}
        </div>

        <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
          Selected {selectedRunIds.length}/{MAX_SELECTED_RUNS}. URL is deep-linkable via `runs=` query param.
        </p>
      </section>

      {runsQuery.isLoading ? <p className="mb-3 text-sm text-[var(--color-text-secondary)]">Loading runs...</p> : null}
      {runsQuery.isError ? (
        <p className="mb-3 rounded-lg border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-3 py-2 text-sm text-[var(--color-error-text)]">
          Failed to load runs list.
        </p>
      ) : null}

      {selectedRunIds.length < 2 ? (
        <p className="mb-3 rounded-lg border border-[var(--color-info-border)] bg-[var(--color-info-bg)] px-3 py-2 text-sm text-[var(--color-info-text)]">
          Select at least 2 runs to populate the comparison table.
        </p>
      ) : null}

      {summaryError ? (
        <p className="mb-3 rounded-lg border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-3 py-2 text-sm text-[var(--color-error-text)]">
          Failed to load one or more run summaries.
        </p>
      ) : null}

      {selectedRunIds.length >= 2 ? (
        <section className="mb-4 overflow-x-auto rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] shadow-[var(--shadow-card)]">
          <CompareGridHeader runIds={selectedRunIds} deltaPairs={deltaPairs} />
          {metricRows.map((row) => (
            <CompareMetricRow key={row.key} row={row} runIds={selectedRunIds} deltaPairs={deltaPairs} />
          ))}
        </section>
      ) : null}

      <section className="mb-4 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Config Diff</h3>
        {configDiff.compared ? (
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
            Comparing `{configDiff.compared[0]}` vs `{configDiff.compared[1]}` (ignoring `runtime.seed`).
          </p>
        ) : (
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Select at least 2 runs to compare configs.</p>
        )}

        {configDiff.compared && configDiff.differences.length === 0 ? (
          <p className="mt-3 rounded-lg border border-[var(--color-info-border)] bg-[var(--color-info-bg)] px-3 py-2 text-sm text-[var(--color-info-text)]">
            Configs are identical (different seeds).
          </p>
        ) : null}

        {configDiff.differences.length > 0 ? (
          <div className="mt-3 max-h-[360px] overflow-auto rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)]">
            {configDiff.differences.map((diff) => (
              <div key={diff.key} className="grid grid-cols-[1.3fr_1fr_1fr] border-b border-[var(--color-border-subtle)] px-3 py-2 text-xs">
                <span className="font-semibold text-[var(--color-text-primary)]">{diff.key}</span>
                <span className="truncate text-[var(--color-text-secondary)]">{diff.left}</span>
                <span className="truncate text-[var(--color-primary-700)]">{diff.right}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Overlaid Charts</h3>
        <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
          Showing up to {MAX_CHART_RUNS} runs for chart overlays to keep charts legible.
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {chartRunIds.map((runId) => {
            const checked = visibleRunIds.includes(runId);
            return (
              <label key={runId} className="inline-flex items-center gap-2 rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-2.5 py-1.5 text-xs">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    setVisibleRunIds((prev) => {
                      if (checked) {
                        return prev.filter((id) => id !== runId);
                      }
                      return [...prev, runId];
                    })
                  }
                />
                {runId}
              </label>
            );
          })}
        </div>

        {qualityError ? (
          <p className="mt-3 rounded-lg border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-3 py-2 text-sm text-[var(--color-error-text)]">
            Failed to load game detail samples for quality overlays.
          </p>
        ) : null}

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <OverlaidPhaseAcplChart runIds={visibleRunIds} metricsByRun={metricsByRun} />
          <OverlaidMoveQualityChart runIds={visibleRunIds} qualityByRun={qualityByRun} />
        </div>

        {qualityLoading ? (
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Loading sampled games for overlay charts...</p>
        ) : null}
      </section>
    </section>
  );
}

function CompareGridHeader({ runIds, deltaPairs }: { runIds: string[]; deltaPairs: Array<[string, string]> }) {
  const columns = buildGridTemplateColumns(runIds.length, deltaPairs.length);
  return (
    <div
      className="grid border-b border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]"
      style={{ gridTemplateColumns: columns }}
    >
      <span>Metric</span>
      {runIds.map((runId) => (
        <span key={runId} className="truncate">
          {runId}
        </span>
      ))}
      {deltaPairs.map(([left, right]) => (
        <span key={`${left}-${right}`} className="truncate">
          Delta {left}{"->"}
          {right}
        </span>
      ))}
    </div>
  );
}

function CompareMetricRow({
  row,
  runIds,
  deltaPairs,
}: {
  row: MetricRow;
  runIds: string[];
  deltaPairs: Array<[string, string]>;
}) {
  const columns = buildGridTemplateColumns(runIds.length, deltaPairs.length);
  return (
    <div className="grid border-b border-[var(--color-border-subtle)] px-3 py-2 text-sm" style={{ gridTemplateColumns: columns }}>
      <span className="font-semibold text-[var(--color-text-primary)]">{row.label}</span>
      {runIds.map((runId) => (
        <span key={`${row.key}-${runId}`} className="text-[var(--color-text-secondary)]">
          {row.valuesByRun[runId]?.text ?? "--"}
        </span>
      ))}
      {deltaPairs.map(([left, right]) => {
        const leftRaw = row.valuesByRun[left]?.raw ?? null;
        const rightRaw = row.valuesByRun[right]?.raw ?? null;
        const delta = buildDeltaLabel(leftRaw, rightRaw, row.direction);
        return (
          <span key={`${row.key}-${left}-${right}`} className={deltaToneClass(delta.tone)}>
            {delta.text}
          </span>
        );
      })}
    </div>
  );
}

function OverlaidPhaseAcplChart({
  runIds,
  metricsByRun,
}: {
  runIds: string[];
  metricsByRun: Map<string, ReturnType<typeof extractRunMetrics>>;
}) {
  const max = useMemo(() => {
    const values = runIds.flatMap((runId) => PHASE_KEYS.map((phase) => metricsByRun.get(runId)?.acplByPhase[phase] ?? null));
    return Math.max(1, ...values.map((value) => (typeof value === "number" && Number.isFinite(value) ? value : 0)));
  }, [metricsByRun, runIds]);

  return (
    <section className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Phase ACPL (overlay)</p>
      <div className="mt-2 space-y-3">
        {PHASE_KEYS.map((phase) => (
          <div key={phase}>
            <p className="text-xs font-semibold text-[var(--color-text-primary)]">{phase}</p>
            <div className="mt-1 space-y-1">
              {runIds.map((runId, index) => {
                const value = metricsByRun.get(runId)?.acplByPhase[phase] ?? null;
                const numeric = typeof value === "number" && Number.isFinite(value) ? value : 0;
                const widthPercent = Math.max(1, (numeric / max) * 100);
                return (
                  <div key={`${phase}-${runId}`} className="flex items-center gap-2">
                    <span className="w-[110px] truncate text-[11px] text-[var(--color-text-secondary)]">{runId}</span>
                    <div className="h-2 w-full rounded bg-[var(--color-neutral-bg)]">
                      <div className={`h-2 rounded ${overlayBarClass(index)}`} style={{ width: `${widthPercent}%` }} />
                    </div>
                    <span className="w-14 text-right text-[11px] text-[var(--color-text-secondary)]">{formatDecimal(value, 1)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function OverlaidMoveQualityChart({
  runIds,
  qualityByRun,
}: {
  runIds: string[];
  qualityByRun: Map<string, MoveQualityCounts>;
}) {
  const max = useMemo(() => {
    const values = runIds.flatMap((runId) =>
      QUALITY_KEYS.map((key) => {
        const counts = qualityByRun.get(runId);
        return counts ? counts[key] : 0;
      }),
    );
    return Math.max(1, ...values);
  }, [qualityByRun, runIds]);

  return (
    <section className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Move quality (overlay)</p>
      <div className="mt-2 space-y-3">
        {QUALITY_KEYS.map((key) => (
          <div key={key}>
            <p className="text-xs font-semibold text-[var(--color-text-primary)]">{key}</p>
            <div className="mt-1 space-y-1">
              {runIds.map((runId, index) => {
                const counts = qualityByRun.get(runId);
                const value = counts ? counts[key] : 0;
                const widthPercent = Math.max(1, (value / max) * 100);
                return (
                  <div key={`${key}-${runId}`} className="flex items-center gap-2">
                    <span className="w-[110px] truncate text-[11px] text-[var(--color-text-secondary)]">{runId}</span>
                    <div className="h-2 w-full rounded bg-[var(--color-neutral-bg)]">
                      <div className={`h-2 rounded ${overlayBarClass(index)}`} style={{ width: `${widthPercent}%` }} />
                    </div>
                    <span className="w-12 text-right text-[11px] text-[var(--color-text-secondary)]">{value}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function buildMetricRows(
  runIds: string[],
  metricsByRun: Map<string, ReturnType<typeof extractRunMetrics>>,
): MetricRow[] {
  const rows: MetricRow[] = [];

  rows.push(
    makeMetricRow(runIds, metricsByRun, "elo", "Elo", "higher", (metrics) => metrics.eloMle, (value) => formatDecimal(value, 1)),
    makeMetricRow(runIds, metricsByRun, "acpl", "ACPL overall", "lower", (metrics) => metrics.acplOverall, (value) => formatDecimal(value, 1)),
    makeMetricRow(
      runIds,
      metricsByRun,
      "acpl_opening",
      "ACPL opening",
      "lower",
      (metrics) => metrics.acplByPhase.opening,
      (value) => formatDecimal(value, 1),
    ),
    makeMetricRow(
      runIds,
      metricsByRun,
      "acpl_middle",
      "ACPL middlegame",
      "lower",
      (metrics) => metrics.acplByPhase.middlegame,
      (value) => formatDecimal(value, 1),
    ),
    makeMetricRow(
      runIds,
      metricsByRun,
      "acpl_endgame",
      "ACPL endgame",
      "lower",
      (metrics) => metrics.acplByPhase.endgame,
      (value) => formatDecimal(value, 1),
    ),
    makeMetricRow(runIds, metricsByRun, "blunder", "Blunder rate", "lower", (metrics) => metrics.blunderRate, (value) => formatRate(value, 1)),
    makeMetricRow(runIds, metricsByRun, "completion", "Completion", "higher", (metrics) => metrics.completionRate, (value) => formatRate(value, 1)),
    makeMetricRow(
      runIds,
      metricsByRun,
      "best_move",
      "Best move agreement",
      "higher",
      (metrics) => metrics.bestMoveAgreement,
      (value) => formatRate(value, 1),
    ),
    makeMetricRow(
      runIds,
      metricsByRun,
      "cost_per_game",
      "Cost per game (USD)",
      "lower",
      (metrics) => divide(metrics.totalCostUsd, metrics.validGames),
      (value) => formatUsd(value, 4),
    ),
    makeMetricRow(
      runIds,
      metricsByRun,
      "latency",
      "P95 latency ms",
      "lower",
      (metrics) => metrics.p95MoveLatencyMs,
      (value) => formatDecimal(value, 0),
    ),
  );

  return rows;
}

function makeMetricRow(
  runIds: string[],
  metricsByRun: Map<string, ReturnType<typeof extractRunMetrics>>,
  key: string,
  label: string,
  direction: MetricDirection,
  pick: (metrics: ReturnType<typeof extractRunMetrics>) => number | null,
  format: (value: number | null) => string,
): MetricRow {
  const valuesByRun: Record<string, RowValue> = {};
  for (const runId of runIds) {
    const metrics = metricsByRun.get(runId);
    const raw = metrics ? pick(metrics) : null;
    valuesByRun[runId] = {
      raw,
      text: format(raw),
    };
  }
  return { key, label, direction, valuesByRun };
}

function buildDeltaPairs(runIds: string[]): Array<[string, string]> {
  const pairs: Array<[string, string]> = [];
  for (let i = 0; i < runIds.length - 1; i += 1) {
    pairs.push([runIds[i], runIds[i + 1]]);
  }
  return pairs;
}

function buildDeltaLabel(left: number | null, right: number | null, direction: MetricDirection): { text: string; tone: DeltaTone } {
  if (left === null || right === null || !Number.isFinite(left) || !Number.isFinite(right)) {
    return { text: "--", tone: "neutral" };
  }
  const diff = right - left;
  if (Math.abs(diff) < 1e-9) {
    return { text: "=", tone: "neutral" };
  }

  const magnitude = Math.abs(diff);
  const text = `${diff > 0 ? "+" : "-"}${formatDeltaNumber(magnitude)}`;

  if (direction === "neutral") {
    return { text, tone: "neutral" };
  }
  if (direction === "higher") {
    return { text, tone: diff > 0 ? "good" : "bad" };
  }
  return { text, tone: diff < 0 ? "good" : "bad" };
}

function formatDeltaNumber(value: number): string {
  if (value >= 100) {
    return value.toFixed(0);
  }
  if (value >= 10) {
    return value.toFixed(1);
  }
  return value.toFixed(3);
}

function buildGridTemplateColumns(runCount: number, deltaCount: number): string {
  const columns = ["220px"];
  for (let i = 0; i < runCount; i += 1) {
    columns.push("minmax(130px, 1fr)");
  }
  for (let i = 0; i < deltaCount; i += 1) {
    columns.push("minmax(120px, 1fr)");
  }
  return columns.join(" ");
}

function deltaToneClass(tone: DeltaTone): string {
  if (tone === "good") {
    return "font-semibold text-[var(--color-success-text)]";
  }
  if (tone === "bad") {
    return "font-semibold text-[var(--color-error-text)]";
  }
  return "text-[var(--color-text-secondary)]";
}

function overlayBarClass(index: number): string {
  const palette = [
    "bg-[#1f637d]",
    "bg-[#8b5a2b]",
    "bg-[#2e7d4f]",
    "bg-[#7b4f9f]",
    "bg-[#b34f62]",
    "bg-[#4b6cb7]",
  ];
  return palette[index % palette.length];
}

function flattenObject(value: unknown, prefix = ""): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return prefix ? { [prefix]: value } : {};
  }

  const out: Record<string, unknown> = {};
  for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      Object.assign(out, flattenObject(nested, path));
    } else {
      out[path] = nested;
    }
  }
  return out;
}

function stableStringify(value: unknown): string {
  if (value === undefined) {
    return "--";
  }
  if (value === null) {
    return "null";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function divide(numerator: number | null, denominator: number | null): number | null {
  if (numerator === null || denominator === null || denominator <= 0) {
    return null;
  }
  return numerator / denominator;
}

function arraysEqual(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) {
      return false;
    }
  }
  return true;
}

function readRunIdsFromUrl(rawSearch: string): string[] {
  const params = new URLSearchParams(rawSearch);
  const value = params.get("runs");
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .slice(0, MAX_SELECTED_RUNS);
}

