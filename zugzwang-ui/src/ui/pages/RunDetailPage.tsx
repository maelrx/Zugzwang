import { useQueryClient, useQueries } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Chessboard } from "react-chessboard";
import { ApiError, apiRequest } from "../../api/client";
import { useGame, useGameFrames, useJob, useRunGames, useRunSummary, useStartEvaluation, useStartRun } from "../../api/queries";
import type { GameDetailResponse, GameListItem, RunSummaryResponse } from "../../api/types";
import { useLabStore } from "../../stores/labStore";
import { MoveQualityDistributionCard } from "../components/MoveQualityDistributionCard";
import { PageHeader } from "../components/PageHeader";
import { PhaseMetricCard } from "../components/PhaseMetricCard";
import { StatusBadge } from "../components/StatusBadge";
import { aggregateMoveQuality } from "../lib/moveQuality";
import { extractRunMetrics, formatCi, formatDecimal, formatRate, formatUsd } from "../lib/runMetrics";

const MAX_QUALITY_GAMES_SAMPLE = 20;
const EMPTY_GAMES: GameListItem[] = [];
const FALLBACK_CONFIG_PATH = "configs/baselines/best_known_start.yaml";
const DEFAULT_BOARD_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

type RunDetailTab = "overview" | "games" | "move-quality" | "config" | "reports";
type InlineMoveQuality = "best" | "good" | "inaccuracy" | "blunder";

export function RunDetailPage() {
  const params = useParams({ strict: false }) as { runId: string };
  const runId = params.runId;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const setLabTemplatePath = useLabStore((state) => state.setSelectedTemplatePath);
  const setLabProvider = useLabStore((state) => state.setSelectedProvider);
  const setLabModel = useLabStore((state) => state.setSelectedModel);
  const setLabOverrides = useLabStore((state) => state.setRawOverridesText);
  const setLabAdvancedOpen = useLabStore((state) => state.setAdvancedOpen);

  const summaryQuery = useRunSummary(runId);
  const gamesQuery = useRunGames(runId, Boolean(summaryQuery.data));
  const startEval = useStartEvaluation();
  const startRun = useStartRun();

  const [activeTab, setActiveTab] = useState<RunDetailTab>(() => readTabFromUrl(window.location.search));
  const [expandedGameNumber, setExpandedGameNumber] = useState<number | null>(() => readExpandedGameFromUrl(window.location.search));
  const [playerColor, setPlayerColor] = useState<"white" | "black">("black");
  const [opponentElo, setOpponentElo] = useState("");
  const [lastEvalJobId, setLastEvalJobId] = useState<string | null>(null);
  const [lastRerunJobId, setLastRerunJobId] = useState<string | null>(null);

  const evalJobQuery = useJob(lastEvalJobId);
  const evalJobStatus = evalJobQuery.data?.status ?? null;
  const evalJobTerminal = evalJobStatus === "completed" || evalJobStatus === "failed" || evalJobStatus === "canceled";

  useEffect(() => {
    if (!lastEvalJobId || !evalJobTerminal) {
      return;
    }
    queryClient.invalidateQueries({ queryKey: ["run-summary", runId] }).catch(() => undefined);
    queryClient.invalidateQueries({ queryKey: ["runs"] }).catch(() => undefined);
  }, [evalJobTerminal, lastEvalJobId, queryClient, runId]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set("tab", activeTab);
    if (expandedGameNumber !== null) {
      params.set("game", String(expandedGameNumber));
    } else {
      params.delete("game");
    }
    const next = params.toString();
    const nextUrl = next.length > 0 ? `${window.location.pathname}?${next}` : window.location.pathname;
    window.history.replaceState(null, "", nextUrl);
  }, [activeTab, expandedGameNumber]);

  const summary = summaryQuery.data;
  const summaryNotFound = isNotFoundError(summaryQuery.error);
  const games = gamesQuery.data ?? EMPTY_GAMES;
  const runMeta = summary?.run_meta;
  const runDir = runMeta?.run_dir ?? "";
  const report = asRecord(summary?.report);
  const evaluatedReport = asRecord(summary?.evaluated_report);
  const evaluationMeta = asRecord(evaluatedReport.evaluation);
  const stockfishMeta = asRecord(evaluationMeta.stockfish);

  const metrics = useMemo(() => extractRunMetrics(summary), [summary]);
  const hasEvaluatedReport = Boolean(runMeta?.evaluated_report_exists && Object.keys(evaluatedReport).length > 0);
  const hasBudgetStop = metrics.stoppedDueToBudget === true;
  const sampledGames = useMemo(() => games.slice(0, MAX_QUALITY_GAMES_SAMPLE), [games]);

  const gameDetailQueries = useQueries({
    queries: sampledGames.map((game) => ({
      queryKey: ["run-detail-game-quality", runId, game.game_number] as const,
      queryFn: () => apiRequest<GameDetailResponse>(`/api/runs/${runId}/games/${game.game_number}`),
      enabled: runId.length > 0,
      staleTime: Infinity,
    })),
  });

  const sampledGameDetails = useMemo(
    () => gameDetailQueries.map((query) => query.data).filter((item): item is GameDetailResponse => Boolean(item)),
    [gameDetailQueries],
  );
  const qualityCounts = useMemo(() => aggregateMoveQuality(sampledGameDetails), [sampledGameDetails]);
  const topBlunders = useMemo(() => buildTopBlunders(sampledGameDetails), [sampledGameDetails]);
  const qualityLoading = gameDetailQueries.some((query) => query.isLoading);
  const qualityError = gameDetailQueries.some((query) => query.isError);

  const opponentEloText = opponentElo.trim();
  const parsedOpponentElo = opponentEloText.length > 0 ? Number.parseInt(opponentEloText, 10) : null;
  const invalidOpponentElo = opponentEloText.length > 0 && !Number.isFinite(parsedOpponentElo);
  const rerunConfigPath = resolveRerunConfigPath(runMeta?.inferred_config_template);
  const rerunOverrides = buildRerunOverrides(summary);

  useEffect(() => {
    if (runMeta?.inferred_player_color === "white" || runMeta?.inferred_player_color === "black") {
      setPlayerColor(runMeta.inferred_player_color);
    }
  }, [runId, runMeta?.inferred_player_color]);

  if (summaryNotFound) {
    return (
      <section>
        <PageHeader eyebrow="Run Detail" title={runId} subtitle="Overview of artifacts, reports and recorded games for this run." />
        <p className="mb-3 rounded-lg border border-[#d7b071] bg-[#fff3de] px-3 py-2 text-sm text-[#7d5618]">
          Artifacts for this run are not available yet. This usually happens when a job is canceled before the first files are written.
        </p>
        <Link to="/dashboard/jobs" className="rounded-md border border-[#d8d1c5] bg-white px-3 py-1.5 text-sm text-[#334c59]">
          Back to jobs
        </Link>
      </section>
    );
  }

  return (
    <section>
      <PageHeader eyebrow="Run Detail" title={runId} subtitle="One-stop analysis surface with metrics, games, replay and run actions." />

      <section className="sticky top-2 z-10 mb-4 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-3 shadow-[var(--shadow-card)]">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          <MetricStripChip label="Elo +/- CI" value={`${formatDecimal(metrics.eloMle, 1)} ${formatCi(metrics.eloCiLower, metrics.eloCiUpper)}`} />
          <MetricStripChip label="ACPL" value={formatDecimal(metrics.acplOverall, 1)} />
          <MetricStripChip label="Blunder Rate" value={formatRate(metrics.blunderRate, 1)} />
          <MetricStripChip label="Completion" value={formatRate(metrics.completionRate, 1)} />
          <MetricStripChip label="Best Move" value={formatRate(metrics.bestMoveAgreement, 1)} />
          <MetricStripChip label="Cost (USD)" value={formatUsd(metrics.totalCostUsd, 4)} />
          <MetricStripChip label="Avg tokens/move" value={formatDecimal(metrics.avgTokensPerMove, 1)} />
        </div>
      </section>

      <section className="mb-4 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-3 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded-md border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-1.5 text-sm font-semibold text-[var(--color-surface-canvas)]"
            onClick={() => {
              const labOverrides = buildCloneOverrides(summary).join("\n");
              setLabTemplatePath(rerunConfigPath);
              setLabProvider(runMeta?.inferred_provider ?? null);
              setLabModel(runMeta?.inferred_model ?? null);
              setLabOverrides(labOverrides);
              setLabAdvancedOpen(true);
              navigate({ to: "/lab" });
            }}
          >
            Clone to Lab
          </button>

          <button
            type="button"
            className="rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-3 py-1.5 text-sm font-semibold text-[var(--color-text-primary)]"
            disabled={startRun.isPending || !rerunConfigPath}
            onClick={() => {
              if (!window.confirm(`Re-run this experiment using ${rerunConfigPath}?\nThis may incur token cost.`)) {
                return;
              }
              setLastRerunJobId(null);
              startRun.mutate(
                {
                  config_path: rerunConfigPath,
                  model_profile: null,
                  overrides: rerunOverrides,
                },
                {
                  onSuccess: (job) => setLastRerunJobId(job.job_id),
                },
              );
            }}
          >
            {startRun.isPending ? "Starting..." : "Re-run"}
          </button>

          <button
            type="button"
            className="rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-3 py-1.5 text-sm font-semibold text-[var(--color-text-primary)]"
            onClick={() => exportRunJson(runId, summary)}
          >
            Export JSON
          </button>

          {!hasEvaluatedReport ? (
            <button
              type="button"
              className="rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-3 py-1.5 text-sm font-semibold text-[var(--color-text-primary)]"
              onClick={() => setActiveTab("overview")}
            >
              Evaluate Now
            </button>
          ) : null}

          {evalJobStatus === "running" || evalJobStatus === "queued" ? <StatusBadge label="evaluating" tone="warning" /> : null}
          {hasEvaluatedReport ? <StatusBadge label="evaluation ready" tone="success" /> : <StatusBadge label="not evaluated" tone="warning" />}
        </div>

        {lastRerunJobId ? (
          <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
            Re-run started:{" "}
            <Link to="/dashboard/jobs/$jobId" params={{ jobId: lastRerunJobId }} className="font-semibold text-[var(--color-primary-700)] underline">
              {lastRerunJobId}
            </Link>
          </p>
        ) : null}

        {lastEvalJobId ? (
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
            Evaluation job:{" "}
            <Link to="/dashboard/jobs/$jobId" params={{ jobId: lastEvalJobId }} className="font-semibold text-[var(--color-primary-700)] underline">
              {lastEvalJobId}
            </Link>
          </p>
        ) : null}
      </section>

      {(summaryQuery.isLoading || gamesQuery.isLoading) ? <p className="mb-3 text-sm text-[#506672]">Loading run artifacts...</p> : null}

      {(summaryQuery.isError || gamesQuery.isError) && !summaryNotFound ? (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff0ed] px-3 py-2 text-sm text-[#8a3434]">Failed to load run detail.</p>
      ) : null}

      {qualityError ? (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff0ed] px-3 py-2 text-sm text-[#8a3434]">
          Failed to load sampled games for move-quality distribution.
        </p>
      ) : null}

      {hasBudgetStop ? (
        <p className="mb-3 rounded-lg border border-[#d7b071] bg-[#fff3de] px-3 py-2 text-sm text-[#7d5618]">
          Run stopped due to budget guardrail.
          {metrics.budgetStopReason ? ` Reason: ${metrics.budgetStopReason}.` : ""}
        </p>
      ) : null}

      <section className="mb-4 flex flex-wrap gap-2">
        <TabButton label="Overview" active={activeTab === "overview"} onClick={() => setActiveTab("overview")} />
        <TabButton label="Games" active={activeTab === "games"} onClick={() => setActiveTab("games")} />
        <TabButton label="Move Quality" active={activeTab === "move-quality"} onClick={() => setActiveTab("move-quality")} />
        <TabButton label="Config" active={activeTab === "config"} onClick={() => setActiveTab("config")} />
        <TabButton label="Reports" active={activeTab === "reports"} onClick={() => setActiveTab("reports")} />
      </section>
      {activeTab === "overview" ? (
        <section className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Run evaluation</h3>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              Trigger manual evaluation for this run. Metrics refresh automatically when the evaluation job completes.
            </p>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-xs text-[var(--color-text-secondary)]">
                Evaluated side
                <select
                  value={playerColor}
                  onChange={(event) => setPlayerColor(event.target.value as "white" | "black")}
                  className="mt-1 w-full rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2 py-1.5 text-sm text-[var(--color-text-primary)]"
                >
                  <option value="white">white</option>
                  <option value="black">black</option>
                </select>
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Opponent Elo (optional)
                <input
                  value={opponentElo}
                  onChange={(event) => setOpponentElo(event.target.value)}
                  placeholder="e.g. 1000"
                  className="mt-1 w-full rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2 py-1.5 text-sm text-[var(--color-text-primary)]"
                />
              </label>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="rounded-md border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-1.5 text-sm font-semibold text-[var(--color-surface-canvas)]"
                disabled={startEval.isPending || !runDir || invalidOpponentElo}
                onClick={() => {
                  setLastEvalJobId(null);
                  startEval.mutate(
                    {
                      run_dir: runDir,
                      player_color: playerColor,
                      opponent_elo: parsedOpponentElo !== null && Number.isFinite(parsedOpponentElo) ? parsedOpponentElo : null,
                      output_filename: "experiment_report_evaluated.json",
                    },
                    {
                      onSuccess: (job) => setLastEvalJobId(job.job_id),
                    },
                  );
                }}
              >
                {startEval.isPending ? "Starting..." : "Evaluate Now"}
              </button>

              <Link to="/dashboard/jobs" className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-3 py-1.5 text-sm text-[var(--color-text-primary)]">
                Open jobs list
              </Link>
            </div>

            {invalidOpponentElo ? (
              <p className="mt-2 rounded-md border border-[#cf8f8f] bg-[#fff1ef] px-2.5 py-1.5 text-xs text-[#8a3434]">
                Opponent Elo must be a valid integer.
              </p>
            ) : null}

            {startEval.isError ? (
              <p className="mt-2 rounded-md border border-[#ce8d8d] bg-[#fff1ef] px-2.5 py-1.5 text-xs text-[#8a3434]">Failed to start evaluation job.</p>
            ) : null}

            <div className="mt-4 rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
                Evaluation status: {hasEvaluatedReport ? "available" : "not generated yet"}
              </p>
              {hasEvaluatedReport ? (
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <MetricInline label="ACPL" value={formatDecimal(metrics.acplOverall, 1)} />
                  <MetricInline label="Blunder rate" value={formatRate(metrics.blunderRate)} />
                  <MetricInline label="Best move agreement" value={formatRate(metrics.bestMoveAgreement)} />
                  <MetricInline label="Elo MLE" value={formatDecimal(metrics.eloMle, 1)} />
                  <MetricInline label="Elo CI 95%" value={formatCi(metrics.eloCiLower, metrics.eloCiUpper)} />
                  <MetricInline label="Provider" value={stringValue(evaluationMeta.provider) ?? "--"} />
                  <MetricInline label="Player color" value={stringValue(evaluationMeta.player_color) ?? "--"} />
                  <MetricInline label="SF depth" value={stringValue(stockfishMeta.depth) ?? "--"} />
                </div>
              ) : (
                <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
                  Run has no `experiment_report_evaluated.json` yet. Start evaluation to generate ACPL/blunder/Elo metrics.
                </p>
              )}
            </div>
          </section>

          <section className="grid gap-4">
            <PhaseMetricCard
              title="ACPL by phase"
              description="Lower is better. Useful to spot opening/middlegame/endgame weaknesses."
              values={metrics.acplByPhase}
              format="decimal"
            />
            <PhaseMetricCard
              title="Retrieval hit-rate by phase"
              description="Higher is better. Indicates whether RAG is being hit per phase."
              values={metrics.retrievalHitRateByPhase}
              format="percent"
            />
          </section>
        </section>
      ) : null}

      {activeTab === "games" ? (
        <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
          <div className="mb-2 grid grid-cols-[0.9fr_1.4fr_1.2fr_1fr_1fr] border-b border-[var(--color-border-subtle)] pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
            <span>Game</span>
            <span>Path</span>
            <span>Replay</span>
            <span>Deep Dive</span>
            <span />
          </div>

          {games.length === 0 && !gamesQuery.isLoading ? <p className="py-3 text-sm text-[var(--color-text-secondary)]">No games found.</p> : null}

          {games.map((game) => {
            const open = expandedGameNumber === game.game_number;
            return (
              <article key={game.game_number} className="border-b border-[var(--color-border-subtle)] py-2">
                <div className="grid grid-cols-[0.9fr_1.4fr_1.2fr_1fr_1fr] items-center gap-2 text-sm text-[var(--color-text-primary)]">
                  <span>#{game.game_number}</span>
                  <span className="truncate text-xs text-[var(--color-text-secondary)]">{game.path}</span>
                  <button
                    type="button"
                    className="w-fit rounded-md border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-2.5 py-1 text-xs font-semibold text-[var(--color-surface-canvas)]"
                    onClick={() => setExpandedGameNumber(open ? null : game.game_number)}
                  >
                    {open ? "Hide replay" : "Replay"}
                  </button>
                  <Link
                    to="/runs/$runId/replay/$gameNumber"
                    params={{ runId, gameNumber: String(game.game_number) }}
                    className="w-fit rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-1 text-xs text-[var(--color-text-primary)]"
                  >
                    Full Analysis
                  </Link>
                  <span />
                </div>

                {open ? (
                  <div className="mt-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
                    <InlineReplay runId={runId} gameNumber={game.game_number} />
                  </div>
                ) : null}
              </article>
            );
          })}
        </section>
      ) : null}

      {activeTab === "move-quality" ? (
        <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <MoveQualityDistributionCard
            title="Move-quality distribution"
            subtitle={`Computed from sampled game moves (up to ${MAX_QUALITY_GAMES_SAMPLE} games).`}
            counts={qualityCounts}
          />

          <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Top blunders/inaccuracies</h3>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Ranked from sampled games by centipawn loss and recovery hints.</p>

            {topBlunders.length === 0 ? (
              <p className="mt-3 text-sm text-[var(--color-text-secondary)]">No move-quality outliers found in sampled games.</p>
            ) : (
              <div className="mt-3 space-y-2">
                {topBlunders.map((entry) => (
                  <div key={entry.key} className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm">
                    <p className="font-semibold text-[var(--color-text-primary)]">
                      Game {entry.gameNumber}, ply {entry.ply}: {entry.moveLabel}
                    </p>
                    <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                      Quality: {entry.quality} | cp_loss: {entry.cpLossText} | retries: {entry.retries}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>
        </section>
      ) : null}

      {activeTab === "config" ? (
        <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
          <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Resolved config</h3>
          <pre className="mt-3 max-h-[520px] overflow-auto rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3 font-['IBM_Plex_Mono'] text-xs text-[var(--color-text-primary)]">
            {toPrettyJson(summary?.resolved_config)}
          </pre>
        </section>
      ) : null}

      {activeTab === "reports" ? (
        <section className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Experiment report</h3>
              <button
                type="button"
                className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-1 text-xs text-[var(--color-text-primary)]"
                onClick={() => downloadJson(`${runId}.experiment_report.json`, summary?.report ?? {})}
              >
                Download JSON
              </button>
            </div>
            <pre className="mt-3 max-h-[420px] overflow-auto rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3 font-['IBM_Plex_Mono'] text-xs text-[var(--color-text-primary)]">
              {toPrettyJson(report)}
            </pre>
          </section>

          <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Evaluated report</h3>
              <button
                type="button"
                className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-1 text-xs text-[var(--color-text-primary)]"
                onClick={() => downloadJson(`${runId}.evaluated_report.json`, summary?.evaluated_report ?? {})}
              >
                Download JSON
              </button>
            </div>
            <pre className="mt-3 max-h-[420px] overflow-auto rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3 font-['IBM_Plex_Mono'] text-xs text-[var(--color-text-primary)]">
              {toPrettyJson(evaluatedReport)}
            </pre>
          </section>
        </section>
      ) : null}

      {qualityLoading ? (
        <p className="mt-3 rounded-lg border border-[#cfd7dc] bg-[#f3f7fa] px-3 py-2 text-sm text-[#48616f]">
          Loading sampled games for move-quality analysis...
        </p>
      ) : null}
    </section>
  );
}

function InlineReplay({ runId, gameNumber }: { runId: string; gameNumber: number }) {
  const gameQuery = useGame(runId, gameNumber);
  const framesQuery = useGameFrames(runId, gameNumber);
  const frames = framesQuery.data ?? [];
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAutoplay, setIsAutoplay] = useState(false);
  const [autoplayMs, setAutoplayMs] = useState(900);

  useEffect(() => {
    setCurrentIndex(0);
    setIsAutoplay(false);
  }, [gameNumber]);

  useEffect(() => {
    if (!isAutoplay || frames.length <= 1) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setCurrentIndex((prev) => {
        const max = Math.max(0, frames.length - 1);
        if (prev >= max) {
          setIsAutoplay(false);
          return prev;
        }
        return prev + 1;
      });
    }, autoplayMs);

    return () => window.clearInterval(intervalId);
  }, [autoplayMs, frames.length, isAutoplay]);
  const safeIndex = Math.max(0, Math.min(currentIndex, Math.max(0, frames.length - 1)));
  const frame = frames[safeIndex];
  const moveRows = useMemo(() => buildInlineMoveRows(gameQuery.data), [gameQuery.data]);
  const selectedPly = numberValue(frame?.ply_number) ?? safeIndex;
  const boardArrow = buildMoveArrow(stringValue(frame?.move_uci));

  return (
    <section>
      {(gameQuery.isLoading || framesQuery.isLoading) ? <p className="text-sm text-[var(--color-text-secondary)]">Loading replay...</p> : null}
      {(gameQuery.isError || framesQuery.isError) ? (
        <p className="rounded-md border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-2.5 py-1.5 text-xs text-[var(--color-error-text)]">
          Failed to load replay data.
        </p>
      ) : null}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2 py-1 text-xs text-[var(--color-text-primary)]"
          onClick={() => {
            setIsAutoplay(false);
            setCurrentIndex((prev) => Math.max(0, prev - 1));
          }}
          disabled={safeIndex <= 0}
        >
          Prev
        </button>
        <button
          type="button"
          className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2 py-1 text-xs text-[var(--color-text-primary)]"
          onClick={() => {
            setIsAutoplay(false);
            setCurrentIndex((prev) => Math.min(Math.max(0, frames.length - 1), prev + 1));
          }}
          disabled={safeIndex >= Math.max(0, frames.length - 1)}
        >
          Next
        </button>
        <button
          type="button"
          className={[
            "rounded-md border px-2 py-1 text-xs",
            isAutoplay
              ? "border-[var(--color-primary-700)] bg-[var(--color-primary-700)] text-[var(--color-surface-canvas)]"
              : "border-[var(--color-border-default)] bg-[var(--color-surface-raised)] text-[var(--color-text-primary)]",
          ].join(" ")}
          onClick={() => setIsAutoplay((prev) => !prev)}
          disabled={frames.length <= 1}
        >
          {isAutoplay ? "Pause" : "Autoplay"}
        </button>
        <label className="text-xs text-[var(--color-text-secondary)]">
          speed
          <select
            value={autoplayMs}
            onChange={(event) => setAutoplayMs(Number(event.target.value))}
            className="ml-1 rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-1.5 py-0.5 text-xs text-[var(--color-text-primary)]"
          >
            <option value={1200}>slow</option>
            <option value={900}>normal</option>
            <option value={600}>fast</option>
          </select>
        </label>
      </div>

      <div className="grid gap-3 lg:grid-cols-[340px_1fr]">
        <article className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-raised)] p-3">
          <div className="mx-auto w-full max-w-[320px]">
            <Chessboard
              options={{
                id: `inline-replay-${runId}-${gameNumber}`,
                position: stringValue(frame?.fen) ?? DEFAULT_BOARD_FEN,
                boardOrientation: "white",
                allowDragging: false,
                allowDrawingArrows: true,
                arrows: boardArrow ? [boardArrow] : [],
                boardStyle: { width: "100%", maxWidth: "320px" },
                darkSquareStyle: { backgroundColor: "#c4a877" },
                lightSquareStyle: { backgroundColor: "#f2dfbf" },
              }}
            />
          </div>
          <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
            frame {safeIndex}/{Math.max(0, frames.length - 1)} | ply {selectedPly}
          </p>
        </article>

        <article className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-raised)] p-3">
          <p className="mb-1 text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Moves</p>
          {moveRows.length === 0 ? (
            <p className="text-sm text-[var(--color-text-secondary)]">No move records.</p>
          ) : (
            <div className="max-h-[260px] overflow-auto rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-2">
              <ol className="space-y-1 text-xs">
                {moveRows.map((move, index) => (
                  <li key={move.key}>
                    <button
                      type="button"
                      className={[
                        "flex w-full items-center justify-between rounded px-2 py-1 text-left",
                        selectedPly === move.ply ? "bg-[var(--color-primary-50)]" : "hover:bg-[var(--color-surface-raised)]",
                      ].join(" ")}
                      onClick={() => setCurrentIndex(index + 1)}
                    >
                      <span className="font-mono text-[var(--color-text-primary)]">
                        {move.ply}. {move.label}
                      </span>
                      <span className={inlineQualityBadgeClass(move.quality)}>{move.quality}</span>
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          )}
          <p className="mt-2 text-xs text-[var(--color-text-secondary)]">FEN: {stringValue(frame?.fen) ?? "--"}</p>
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">UCI: {stringValue(frame?.move_uci) ?? "--"}</p>
        </article>
      </div>
    </section>
  );
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "rounded-full border px-3 py-1.5 text-sm",
        active
          ? "border-[var(--color-primary-700)] bg-[var(--color-primary-700)] text-[var(--color-surface-canvas)]"
          : "border-[var(--color-border-default)] bg-[var(--color-surface-raised)] text-[var(--color-text-primary)]",
      ].join(" ")}
    >
      {label}
    </button>
  );
}

function MetricStripChip({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">{value}</p>
    </article>
  );
}

function MetricInline({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-surface-raised)] px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-1 text-xs font-semibold text-[var(--color-text-primary)]">{value}</p>
    </div>
  );
}

function readTabFromUrl(rawSearch: string): RunDetailTab {
  const params = new URLSearchParams(rawSearch);
  const tab = params.get("tab");
  if (tab === "overview" || tab === "games" || tab === "move-quality" || tab === "config" || tab === "reports") {
    return tab;
  }
  return "overview";
}

function readExpandedGameFromUrl(rawSearch: string): number | null {
  const params = new URLSearchParams(rawSearch);
  const game = params.get("game");
  if (!game) {
    return null;
  }
  const parsed = Number.parseInt(game, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function resolveRerunConfigPath(inferredTemplate: string | null | undefined): string {
  if (!inferredTemplate || inferredTemplate.trim().length === 0) {
    return FALLBACK_CONFIG_PATH;
  }
  if (inferredTemplate.endsWith(".yaml")) {
    return inferredTemplate;
  }
  return FALLBACK_CONFIG_PATH;
}

function buildCloneOverrides(summary: RunSummaryResponse | undefined): string[] {
  const runMeta = summary?.run_meta;
  const overrides: string[] = [];
  if (runMeta?.inferred_provider) {
    overrides.push(`players.black.provider=${runMeta.inferred_provider}`);
  }
  if (runMeta?.inferred_model) {
    overrides.push(`players.black.model=${runMeta.inferred_model}`);
  }
  if (runMeta?.inferred_player_color) {
    overrides.push(`evaluation.auto.player_color=${runMeta.inferred_player_color}`);
  }
  if (typeof runMeta?.inferred_opponent_elo === "number") {
    overrides.push(`evaluation.auto.opponent_elo=${runMeta.inferred_opponent_elo}`);
  }
  overrides.push(`evaluation.auto.enabled=${runMeta?.evaluated_report_exists ? "true" : "false"}`);
  return overrides;
}

function buildRerunOverrides(summary: RunSummaryResponse | undefined): string[] {
  const runMeta = summary?.run_meta;
  const overrides: string[] = [];
  if (runMeta?.inferred_provider) {
    overrides.push("players.black.type=llm");
    overrides.push(`players.black.provider=${runMeta.inferred_provider}`);
  }
  if (runMeta?.inferred_model) {
    overrides.push(`players.black.model=${runMeta.inferred_model}`);
  }
  if (runMeta?.inferred_player_color) {
    overrides.push(`evaluation.auto.player_color=${runMeta.inferred_player_color}`);
  }
  if (typeof runMeta?.inferred_opponent_elo === "number") {
    overrides.push(`evaluation.auto.opponent_elo=${runMeta.inferred_opponent_elo}`);
  }
  overrides.push(`evaluation.auto.enabled=${runMeta?.evaluated_report_exists ? "true" : "false"}`);
  overrides.push(`runtime.seed=${Math.floor(Date.now() % 2_000_000_000)}`);
  return overrides;
}
function exportRunJson(runId: string, summary: RunSummaryResponse | undefined): void {
  downloadJson(`${runId}.full_export.json`, summary ?? {});
}

function downloadJson(filename: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(href);
}

function buildTopBlunders(
  gameDetails: GameDetailResponse[],
): Array<{ key: string; gameNumber: number; ply: number; moveLabel: string; quality: string; cpLossText: string; retries: number }> {
  const out: Array<{ key: string; gameNumber: number; ply: number; moveLabel: string; quality: string; cpLoss: number; cpLossText: string; retries: number }> = [];

  for (const game of gameDetails) {
    const gameNumber = numberValue(game.game_number) ?? 0;
    const moves = game.moves ?? [];
    for (let index = 0; index < moves.length; index += 1) {
      const move = asRecord(moves[index]);
      const decision = asRecord(move.move_decision);
      const ply = numberValue(move.ply_number) ?? index + 1;
      const moveLabel = stringValue(decision.move_san) ?? stringValue(decision.move_uci) ?? "(unknown)";
      const quality = classifyInlineQuality(decision);
      if (quality !== "blunder" && quality !== "inaccuracy") {
        continue;
      }
      const cpLoss = numberValue(decision.cp_loss) ?? numberValue(decision.centipawn_loss) ?? (quality === "blunder" ? 500 : 120);
      const retries = numberValue(decision.retry_count) ?? 0;
      out.push({
        key: `${gameNumber}-${ply}-${moveLabel}`,
        gameNumber,
        ply,
        moveLabel,
        quality,
        cpLoss,
        cpLossText: Number.isFinite(cpLoss) ? cpLoss.toFixed(0) : "--",
        retries,
      });
    }
  }

  return out.sort((a, b) => b.cpLoss - a.cpLoss).slice(0, 12).map(({ cpLoss, ...rest }) => rest);
}

function buildInlineMoveRows(game: GameDetailResponse | undefined): Array<{ key: string; ply: number; label: string; quality: InlineMoveQuality }> {
  const moves = game?.moves ?? [];
  return moves.map((entry, index) => {
    const move = asRecord(entry);
    const decision = asRecord(move.move_decision);
    const ply = numberValue(move.ply_number) ?? index + 1;
    const label = stringValue(decision.move_san) ?? stringValue(decision.move_uci) ?? "(unknown)";
    return {
      key: `${ply}-${label}`,
      ply,
      label,
      quality: classifyInlineQuality(decision),
    };
  });
}

function classifyInlineQuality(decision: Record<string, unknown>): InlineMoveQuality {
  const cpLoss = numberValue(decision.cp_loss) ?? numberValue(decision.centipawn_loss);
  if (cpLoss !== null) {
    if (cpLoss <= 20) {
      return "best";
    }
    if (cpLoss <= 80) {
      return "good";
    }
    if (cpLoss <= 200) {
      return "inaccuracy";
    }
    return "blunder";
  }

  const isLegal = booleanValue(decision.is_legal);
  const retryCount = numberValue(decision.retry_count) ?? 0;
  if (isLegal === false) {
    return "blunder";
  }
  if (retryCount > 0) {
    return "inaccuracy";
  }
  return "good";
}

function inlineQualityBadgeClass(quality: InlineMoveQuality): string {
  if (quality === "best") {
    return "rounded-full border border-[#8ec9a0] bg-[#e7f8ee] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#235f3d]";
  }
  if (quality === "good") {
    return "rounded-full border border-[#9bb1c7] bg-[#ecf2f8] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#2a4c67]";
  }
  if (quality === "inaccuracy") {
    return "rounded-full border border-[#d7b071] bg-[#fff3de] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#865d1a]";
  }
  return "rounded-full border border-[#d29292] bg-[#ffe8e8] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#8d3131]";
}

function buildMoveArrow(moveUci: string | null | undefined): { startSquare: string; endSquare: string; color: string } | null {
  if (!moveUci || moveUci.length < 4) {
    return null;
  }
  const startSquare = moveUci.slice(0, 2);
  const endSquare = moveUci.slice(2, 4);
  if (!isBoardSquare(startSquare) || !isBoardSquare(endSquare)) {
    return null;
  }
  return { startSquare, endSquare, color: "#1f637d99" };
}

function isBoardSquare(value: string): boolean {
  return /^[a-h][1-8]$/.test(value);
}

function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

function toPrettyJson(value: unknown): string {
  if (value === null || value === undefined) {
    return "{}";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function stringValue(value: unknown): string | null {
  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

function numberValue(value: unknown): number | null {
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

function booleanValue(value: unknown): boolean | null {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    if (value.toLowerCase() === "true") {
      return true;
    }
    if (value.toLowerCase() === "false") {
      return false;
    }
  }
  return null;
}
