import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { useModelCatalog, useRuns } from "../../api/queries";
import { useCompareStore } from "../../stores/compareStore";
import { PageHeader } from "../components/PageHeader";
import { formatDecimal, formatUsd } from "../lib/runMetrics";

const PAGE_SIZE = 50;

type SortBy = "created_at_utc" | "run_id" | "total_cost_usd" | "elo_estimate" | "acpl_overall";
type SortDir = "asc" | "desc";

type RunsSearchState = {
  q: string;
  provider: string;
  evaluatedOnly: boolean;
  dateFrom: string;
  dateTo: string;
  sortBy: SortBy;
  sortDir: SortDir;
  page: number;
};

export function RunsPage() {
  const navigate = useNavigate();
  const modelCatalogQuery = useModelCatalog();
  const selectedRunIds = useCompareStore((state) => state.selectedRunIds);
  const toggleRunSelection = useCompareStore((state) => state.toggleRunSelection);
  const setSelection = useCompareStore((state) => state.setSelection);
  const clearSelection = useCompareStore((state) => state.clearSelection);

  const [filters, setFilters] = useState<RunsSearchState>(() => readRunsSearchFromUrl(window.location.search));
  const [queryInput, setQueryInput] = useState(filters.q);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setFilters((prev) => ({ ...prev, q: queryInput.trim(), page: 1 }));
    }, 200);
    return () => window.clearTimeout(timeout);
  }, [queryInput]);

  useEffect(() => {
    const params = buildRunsSearchParams(filters);
    const next = params.toString();
    const nextUrl = next.length > 0 ? `${window.location.pathname}?${next}` : window.location.pathname;
    window.history.replaceState(null, "", nextUrl);
  }, [filters]);

  const runsQuery = useRuns({
    q: filters.q || undefined,
    evaluatedOnly: filters.evaluatedOnly || undefined,
    provider: filters.provider || undefined,
    dateFrom: filters.dateFrom || undefined,
    dateTo: filters.dateTo || undefined,
    sortBy: filters.sortBy,
    sortDir: filters.sortDir,
    offset: (filters.page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
  });
  const runs = runsQuery.data ?? [];

  const providerOptions = useMemo(() => {
    const catalog = (modelCatalogQuery.data ?? []).map((item) => item.provider);
    const inferred = runs.map((run) => run.inferred_provider).filter((item): item is string => typeof item === "string" && item.length > 0);
    const merged = [...new Set([...catalog, ...inferred])];
    return merged.sort((a, b) => a.localeCompare(b));
  }, [modelCatalogQuery.data, runs]);

  const hasNextPage = runs.length >= PAGE_SIZE;
  const hasPrevPage = filters.page > 1;
  const compareCount = selectedRunIds.length;

  return (
    <section>
      <PageHeader
        eyebrow="Runs"
        title="Run Explorer"
        subtitle="Filter, sort and select runs for comparison. Open detail, replay, clone and rerun flows from one index."
      />

      <section className="mb-4 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <div className="grid gap-3 lg:grid-cols-[1.6fr_0.9fr_0.6fr_0.8fr_0.8fr_auto]">
          <label className="text-xs text-[var(--color-text-secondary)]">
            Search run/model
            <input
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="run_id or model..."
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            />
          </label>

          <label className="text-xs text-[var(--color-text-secondary)]">
            Provider
            <select
              value={filters.provider}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  provider: event.target.value,
                  page: 1,
                }))
              }
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            >
              <option value="">All providers</option>
              {providerOptions.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </select>
          </label>

          <label className="inline-flex items-center gap-2 self-end pb-1 text-sm text-[var(--color-text-primary)]">
            <input
              type="checkbox"
              checked={filters.evaluatedOnly}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  evaluatedOnly: event.target.checked,
                  page: 1,
                }))
              }
              className="h-4 w-4 rounded border-[var(--color-border-strong)]"
            />
            Evaluated only
          </label>

          <label className="text-xs text-[var(--color-text-secondary)]">
            Date from
            <input
              type="date"
              value={filters.dateFrom}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  dateFrom: event.target.value,
                  page: 1,
                }))
              }
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            />
          </label>

          <label className="text-xs text-[var(--color-text-secondary)]">
            Date to
            <input
              type="date"
              value={filters.dateTo}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  dateTo: event.target.value,
                  page: 1,
                }))
              }
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            />
          </label>

          <div className="flex items-end justify-end gap-2">
            <button
              type="button"
              className="rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
              onClick={() => {
                const reset = defaultRunsSearch();
                setFilters(reset);
                setQueryInput("");
                clearSelection();
              }}
            >
              Reset
            </button>
            <button
              type="button"
              disabled={compareCount < 2}
              className="rounded-lg border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-2 text-sm font-semibold text-[var(--color-surface-canvas)] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => {
                setSelection(selectedRunIds);
                navigate({ to: "/runs/compare" });
              }}
            >
              Compare Selected ({compareCount})
            </button>
          </div>
        </div>
      </section>

      <section className="overflow-x-auto rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] shadow-[var(--shadow-card)]">
        <div className="grid min-w-[1080px] grid-cols-[42px_2.2fr_1.5fr_0.8fr_0.8fr_0.8fr_0.8fr_0.8fr_0.9fr_1fr] border-b border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
          <span />
          <SortHeader
            label="Run ID"
            active={filters.sortBy === "run_id"}
            direction={filters.sortDir}
            onClick={() => setFilters((prev) => flipSort(prev, "run_id"))}
          />
          <span>Model</span>
          <span>Games</span>
          <SortHeader
            label="Elo"
            active={filters.sortBy === "elo_estimate"}
            direction={filters.sortDir}
            onClick={() => setFilters((prev) => flipSort(prev, "elo_estimate"))}
          />
          <SortHeader
            label="ACPL"
            active={filters.sortBy === "acpl_overall"}
            direction={filters.sortDir}
            onClick={() => setFilters((prev) => flipSort(prev, "acpl_overall"))}
          />
          <SortHeader
            label="Cost"
            active={filters.sortBy === "total_cost_usd"}
            direction={filters.sortDir}
            onClick={() => setFilters((prev) => flipSort(prev, "total_cost_usd"))}
          />
          <span>Status</span>
          <span>Provider</span>
          <SortHeader
            label="Created"
            active={filters.sortBy === "created_at_utc"}
            direction={filters.sortDir}
            onClick={() => setFilters((prev) => flipSort(prev, "created_at_utc"))}
          />
        </div>

        {runsQuery.isLoading ? (
          <p className="px-4 py-5 text-sm text-[var(--color-text-secondary)]">Loading runs...</p>
        ) : null}

        {runsQuery.isError ? (
          <p className="px-4 py-5 text-sm text-[var(--color-error-text)]">Failed to load runs.</p>
        ) : null}

        {!runsQuery.isLoading && !runsQuery.isError && runs.length === 0 ? (
          <p className="px-4 py-5 text-sm text-[var(--color-text-secondary)]">No runs found for the current filters.</p>
        ) : null}

        {runs.map((run) => {
          const isSelected = selectedRunIds.includes(run.run_id);
          return (
            <div
              key={run.run_id}
              role="button"
              tabIndex={0}
              onClick={() => navigate({ to: "/runs/$runId", params: { runId: run.run_id } })}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  navigate({ to: "/runs/$runId", params: { runId: run.run_id } });
                }
              }}
              className="grid min-w-[1080px] cursor-pointer grid-cols-[42px_2.2fr_1.5fr_0.8fr_0.8fr_0.8fr_0.8fr_0.8fr_0.9fr_1fr] items-center border-b border-[var(--color-border-subtle)] px-3 py-2.5 text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-surface-canvas)]"
            >
              <input
                type="checkbox"
                checked={isSelected}
                onClick={(event) => event.stopPropagation()}
                onChange={() => toggleRunSelection(run.run_id)}
                className="h-4 w-4 rounded border-[var(--color-border-strong)]"
                aria-label={`Select ${run.run_id} for comparison`}
              />

              <Link
                to="/runs/$runId"
                params={{ runId: run.run_id }}
                className="truncate font-semibold text-[var(--color-primary-700)] hover:underline"
                onClick={(event) => event.stopPropagation()}
              >
                {run.run_id}
              </Link>

              <span className="truncate text-xs text-[var(--color-text-secondary)]">
                {run.inferred_model_label ?? run.inferred_model ?? "--"}
              </span>
              <span>{formatGames(run.num_games_valid, run.num_games_target)}</span>
              <span>{formatDecimal(run.elo_estimate, 1)}</span>
              <span>{formatDecimal(run.acpl_overall, 1)}</span>
              <span>{formatUsd(run.total_cost_usd, 4)}</span>
              <span>{resolveEvalStatus(run.inferred_eval_status, run.evaluated_report_exists)}</span>
              <span className="truncate text-xs text-[var(--color-text-secondary)]">{run.inferred_provider ?? "--"}</span>
              <span className="text-xs text-[var(--color-text-secondary)]">{formatCreatedAt(run.created_at_utc)}</span>
            </div>
          );
        })}
      </section>

      <section className="mt-3 flex items-center justify-between">
        <p className="text-xs text-[var(--color-text-secondary)]">
          Page {filters.page} | Showing up to {PAGE_SIZE} rows
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!hasPrevPage}
            onClick={() => setFilters((prev) => ({ ...prev, page: Math.max(1, prev.page - 1) }))}
            className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-3 py-1.5 text-sm text-[var(--color-text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={!hasNextPage}
            onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
            className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-3 py-1.5 text-sm text-[var(--color-text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </section>
    </section>
  );
}

function SortHeader({
  label,
  active,
  direction,
  onClick,
}: {
  label: string;
  active: boolean;
  direction: SortDir;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className="text-left text-[11px] font-semibold uppercase tracking-[0.12em]">
      {label}
      {active ? (direction === "asc" ? " (asc)" : " (desc)") : ""}
    </button>
  );
}

function flipSort(state: RunsSearchState, sortBy: SortBy): RunsSearchState {
  if (state.sortBy === sortBy) {
    return {
      ...state,
      sortDir: state.sortDir === "asc" ? "desc" : "asc",
      page: 1,
    };
  }
  return {
    ...state,
    sortBy,
    sortDir: sortBy === "run_id" ? "asc" : "desc",
    page: 1,
  };
}

function defaultRunsSearch(): RunsSearchState {
  return {
    q: "",
    provider: "",
    evaluatedOnly: false,
    dateFrom: "",
    dateTo: "",
    sortBy: "created_at_utc",
    sortDir: "desc",
    page: 1,
  };
}

function readRunsSearchFromUrl(rawSearch: string): RunsSearchState {
  const defaults = defaultRunsSearch();
  const params = new URLSearchParams(rawSearch);

  const sortBy = params.get("sort_by");
  const sortDir = params.get("sort_dir");
  const pageRaw = params.get("page");
  const pageParsed = pageRaw ? Number.parseInt(pageRaw, 10) : 1;

  return {
    q: params.get("q") ?? defaults.q,
    provider: params.get("provider") ?? defaults.provider,
    evaluatedOnly: params.get("evaluated_only") === "true",
    dateFrom: params.get("date_from") ?? defaults.dateFrom,
    dateTo: params.get("date_to") ?? defaults.dateTo,
    sortBy: isSortBy(sortBy) ? sortBy : defaults.sortBy,
    sortDir: sortDir === "asc" || sortDir === "desc" ? sortDir : defaults.sortDir,
    page: Number.isFinite(pageParsed) && pageParsed > 0 ? pageParsed : 1,
  };
}

function buildRunsSearchParams(filters: RunsSearchState): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q) {
    params.set("q", filters.q);
  }
  if (filters.provider) {
    params.set("provider", filters.provider);
  }
  if (filters.evaluatedOnly) {
    params.set("evaluated_only", "true");
  }
  if (filters.dateFrom) {
    params.set("date_from", filters.dateFrom);
  }
  if (filters.dateTo) {
    params.set("date_to", filters.dateTo);
  }
  params.set("sort_by", filters.sortBy);
  params.set("sort_dir", filters.sortDir);
  if (filters.page > 1) {
    params.set("page", String(filters.page));
  }
  return params;
}

function isSortBy(value: string | null): value is SortBy {
  return value === "created_at_utc" || value === "run_id" || value === "total_cost_usd" || value === "elo_estimate" || value === "acpl_overall";
}

function formatGames(valid: number | null | undefined, target: number | null | undefined): string {
  const validText = typeof valid === "number" ? String(valid) : "--";
  const targetText = typeof target === "number" ? String(target) : "--";
  return `${validText}/${targetText}`;
}

function resolveEvalStatus(
  inferredStatus: "pending_report" | "needs_eval" | "evaluated" | null | undefined,
  evaluatedReportExists: boolean,
): string {
  if (inferredStatus) {
    return inferredStatus;
  }
  return evaluatedReportExists ? "evaluated" : "needs_eval";
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

