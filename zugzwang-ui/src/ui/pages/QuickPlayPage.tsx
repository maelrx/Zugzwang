import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Chessboard } from "react-chessboard";
import { ApiError, apiRequest } from "../../api/client";
import { useConfigs, useEnvCheck, useJob, useJobProgress, useModelCatalog, useRunSummary, useStartPlay } from "../../api/queries";
import type { GameDetailResponse, GameListItem, JobResponse, StartJobRequest } from "../../api/types";
import { useLabStore } from "../../stores/labStore";
import { usePreferencesStore } from "../../stores/preferencesStore";
import { PageHeader } from "../components/PageHeader";
import { ProgressBar } from "../components/ProgressBar";
import { StatusBadge } from "../components/StatusBadge";
import { extractRunMetrics, formatDecimal, formatRate, formatUsd } from "../lib/runMetrics";

const FALLBACK_CONFIG_PATH = "configs/baselines/best_known_start.yaml";
const ADVANCED_OPEN_SESSION_KEY = "zugzwang-quick-play-advanced-open";
const DEFAULT_BOARD_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const RUN_ARTIFACTS_BOOTSTRAP_DELAY_MS = 4_000;

type BoardFormat = "fen" | "pgn";
type FeedbackLevel = "minimal" | "moderate" | "rich";
type OpponentMode = "random" | "stockfish";

export function QuickPlayPage() {
  const navigate = useNavigate();
  const configsQuery = useConfigs();
  const modelCatalogQuery = useModelCatalog();
  const envCheckQuery = useEnvCheck();
  const startPlayMutation = useStartPlay();

  const defaultProvider = usePreferencesStore((state) => state.defaultProvider);
  const defaultModel = usePreferencesStore((state) => state.defaultModel);
  const autoEvaluatePreference = usePreferencesStore((state) => state.autoEvaluate);
  const stockfishDepthPreference = usePreferencesStore((state) => state.stockfishDepth);
  const setDefaultProvider = usePreferencesStore((state) => state.setDefaultProvider);
  const setDefaultModel = usePreferencesStore((state) => state.setDefaultModel);
  const setAutoEvaluatePreference = usePreferencesStore((state) => state.setAutoEvaluate);
  const setStockfishDepthPreference = usePreferencesStore((state) => state.setStockfishDepth);

  const setLabTemplatePath = useLabStore((state) => state.setSelectedTemplatePath);
  const setLabProvider = useLabStore((state) => state.setSelectedProvider);
  const setLabModel = useLabStore((state) => state.setSelectedModel);
  const setLabOverrides = useLabStore((state) => state.setRawOverridesText);
  const setLabAdvancedOpen = useLabStore((state) => state.setAdvancedOpen);

  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [boardFormat, setBoardFormat] = useState<BoardFormat>("fen");
  const [provideLegalMoves, setProvideLegalMoves] = useState(true);
  const [provideHistory, setProvideHistory] = useState(true);
  const [feedbackLevel, setFeedbackLevel] = useState<FeedbackLevel>("rich");
  const [opponentMode, setOpponentMode] = useState<OpponentMode>("random");
  const [stockfishLevel, setStockfishLevel] = useState(stockfishDepthPreference);
  const [rawOverridesText, setRawOverridesText] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(loadAdvancedOpen());
  const [autoEvaluateEnabled, setAutoEvaluateEnabled] = useState<boolean>(autoEvaluatePreference);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runArtifactsReadyAt, setRunArtifactsReadyAt] = useState<number | null>(null);

  const providerPresets = modelCatalogQuery.data ?? [];
  const envChecks = envCheckQuery.data ?? [];
  const providerStatusMap = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const item of envChecks) {
      map.set(normalizeProviderId(item.provider), item.ok);
    }
    return map;
  }, [envChecks]);
  const stockfishCheckKnown = useMemo(() => envChecks.some((item) => item.provider === "stockfish"), [envChecks]);
  const stockfishAvailable = providerStatusMap.get("stockfish") === true;
  const selectedProviderId = normalizeProviderId(selectedProvider);

  const configuredProviders = useMemo(
    () => providerPresets.filter((preset) => providerStatusMap.get(normalizeProviderId(preset.provider)) === true),
    [providerPresets, providerStatusMap],
  );
  const hasConfiguredProvider = configuredProviders.length > 0;
  const selectedProviderReady = providerStatusMap.get(selectedProviderId) === true;
  const activePreset = useMemo(
    () => providerPresets.find((preset) => normalizeProviderId(preset.provider) === selectedProviderId) ?? null,
    [providerPresets, selectedProviderId],
  );

  useEffect(() => {
    if (providerPresets.length === 0) {
      return;
    }

    if (selectedProvider && selectedProvider !== selectedProviderId) {
      setSelectedProvider(selectedProviderId);
      return;
    }

    const selectedStillExists = providerPresets.some((preset) => normalizeProviderId(preset.provider) === selectedProviderId);
    if (selectedProviderId && selectedStillExists) {
      return;
    }

    const defaultProviderId = normalizeProviderId(defaultProvider ?? "");
    const byDefault = defaultProviderId
      ? providerPresets.find((preset) => normalizeProviderId(preset.provider) === defaultProviderId)
      : undefined;
    const preferredProvider = byDefault ?? configuredProviders[0] ?? providerPresets[0];
    setSelectedProvider(normalizeProviderId(preferredProvider?.provider ?? ""));
  }, [configuredProviders, defaultProvider, providerPresets, selectedProvider, selectedProviderId]);

  useEffect(() => {
    if (!activePreset) {
      setSelectedModel("");
      return;
    }

    const hasSelected = activePreset.models.some((item) => item.id === selectedModel);
    if (hasSelected) {
      return;
    }

    const defaultMatch = defaultModel ? activePreset.models.find((item) => item.id === defaultModel) : undefined;
    const fallback = activePreset.models.find((item) => item.recommended) ?? activePreset.models[0] ?? null;
    setSelectedModel(defaultMatch?.id ?? fallback?.id ?? "");
  }, [activePreset, defaultModel, selectedModel]);

  useEffect(() => {
    if (selectedProviderId) {
      setDefaultProvider(selectedProviderId);
    }
  }, [selectedProviderId, setDefaultProvider]);

  useEffect(() => {
    if (selectedModel) {
      setDefaultModel(selectedModel);
    }
  }, [selectedModel, setDefaultModel]);

  useEffect(() => {
    persistAdvancedOpen(advancedOpen);
  }, [advancedOpen]);

  useEffect(() => {
    if (!envCheckQuery.isSuccess || !stockfishCheckKnown || stockfishAvailable) {
      return;
    }
    if (autoEvaluateEnabled) {
      setAutoEvaluateEnabled(false);
      setAutoEvaluatePreference(false);
    }
  }, [autoEvaluateEnabled, envCheckQuery.isSuccess, setAutoEvaluatePreference, stockfishAvailable, stockfishCheckKnown]);

  useEffect(() => {
    if (stockfishDepthPreference !== stockfishLevel) {
      setStockfishLevel(stockfishDepthPreference);
    }
  }, [stockfishDepthPreference, stockfishLevel]);

  useEffect(() => {
    setStockfishDepthPreference(stockfishLevel);
  }, [setStockfishDepthPreference, stockfishLevel]);

  const jobQuery = useJob(activeJobId);
  const progressQuery = useJobProgress(activeJobId);

  const activeJob = jobQuery.data;
  const activeJobStatus = activeJob?.status ?? null;
  const runId = activeJob?.run_id ?? activeRunId;
  const runIdForSummary = runId && isTerminalStatus(activeJobStatus) ? runId : null;
  const summaryQuery = useRunSummary(runIdForSummary);
  const summaryMetrics = useMemo(() => extractRunMetrics(summaryQuery.data), [summaryQuery.data]);
  const latestReport = asRecord(progressQuery.data?.latest_report);
  const isRunning = activeJobStatus === "running" || activeJobStatus === "queued";
  const isTerminal = isTerminalStatus(activeJobStatus);
  const artifactsDelayElapsed = runArtifactsReadyAt === null || Date.now() >= runArtifactsReadyAt;
  const canQueryRunArtifacts = Boolean(runId) && (isTerminal || (progressQuery.isSuccess && artifactsDelayElapsed));

  const gamesQuery = useQuery({
    queryKey: ["quick-play-games", runId] as const,
    queryFn: () => apiRequest<GameListItem[]>(`/api/runs/${runId}/games`),
    enabled: canQueryRunArtifacts,
    staleTime: 0,
    refetchInterval: isRunning ? 2_000 : false,
    retry: shouldRetryWithout404,
  });

  const firstGameNumber = gamesQuery.data?.[0]?.game_number ?? null;
  const gameQuery = useQuery({
    queryKey: ["quick-play-game", runId, firstGameNumber] as const,
    queryFn: () => apiRequest<GameDetailResponse>(`/api/runs/${runId}/games/${firstGameNumber}`),
    enabled: canQueryRunArtifacts && firstGameNumber !== null,
    staleTime: 0,
    refetchInterval: isRunning ? 2_000 : false,
    retry: shouldRetryWithout404,
  });

  const framesQuery = useQuery({
    queryKey: ["quick-play-frames", runId, firstGameNumber] as const,
    queryFn: () => apiRequest<Array<Record<string, unknown>>>(`/api/runs/${runId}/games/${firstGameNumber}/frames`),
    enabled: canQueryRunArtifacts && firstGameNumber !== null,
    staleTime: 0,
    refetchInterval: isRunning ? 2_000 : false,
    retry: shouldRetryWithout404,
  });

  const chosenConfigPath = useMemo(() => {
    const baselines = configsQuery.data?.baselines ?? [];
    const preferred = baselines.find((item) => item.name === "best_known_start");
    return preferred?.path ?? baselines[0]?.path ?? FALLBACK_CONFIG_PATH;
  }, [configsQuery.data?.baselines]);

  const parsedCustomOverrides = useMemo(() => parseOverrides(rawOverridesText), [rawOverridesText]);
  const invalidOverrideLines = useMemo(
    () => parsedCustomOverrides.filter((line) => !line.includes("=")),
    [parsedCustomOverrides],
  );

  const liveFrames = framesQuery.data ?? [];
  const latestFrame = liveFrames[liveFrames.length - 1];
  const latestFen = stringValue(latestFrame?.fen) ?? DEFAULT_BOARD_FEN;
  const latestMoveUci = stringValue(latestFrame?.move_uci);
  const boardArrow = buildMoveArrow(latestMoveUci);

  const moveRows = useMemo(() => {
    const moves = gameQuery.data?.moves ?? [];
    return moves.map((entry, index) => {
      const move = asRecord(entry);
      const decision = asRecord(move.move_decision);
      const ply = numberValue(move.ply_number) ?? index + 1;
      const san = stringValue(decision.move_san);
      const uci = stringValue(decision.move_uci);
      return {
        key: `${ply}-${san ?? uci ?? "move"}`,
        ply,
        label: san ?? uci ?? "(unknown)",
      };
    });
  }, [gameQuery.data?.moves]);

  const tokenUsage = useMemo(() => asRecord(gameQuery.data?.total_tokens), [gameQuery.data?.total_tokens]);
  const tokensInput = numberValue(tokenUsage.input);
  const tokensOutput = numberValue(tokenUsage.output);
  const totalTokens = (tokensInput ?? 0) + (tokensOutput ?? 0);
  const totalCost = numberValue(gameQuery.data?.total_cost_usd) ?? numberValue(latestReport.total_cost_usd);
  const canStartGame =
    Boolean(selectedProviderId) &&
    Boolean(selectedModel) &&
    selectedProviderReady &&
    invalidOverrideLines.length === 0 &&
    !startPlayMutation.isPending;

  const hasLiveData = firstGameNumber !== null && (moveRows.length > 0 || liveFrames.length > 0);
  const resultLabel = gameQuery.data?.result ?? "--";
  const resultTermination = gameQuery.data?.termination ?? "--";
  const resultMoves = moveRows.length;
  const resultDuration = numberValue(gameQuery.data?.duration_seconds);

  const showNoProviderConfigured = envCheckQuery.isSuccess && modelCatalogQuery.isSuccess && !hasConfiguredProvider;
  const runArtifactError =
    extractRunArtifactError(gamesQuery.error, isRunning) ||
    extractRunArtifactError(gameQuery.error, isRunning) ||
    extractRunArtifactError(framesQuery.error, isRunning);
  const statusError =
    extractError(startPlayMutation.error) ||
    extractError(jobQuery.error) ||
    extractError(progressQuery.error) ||
    runArtifactError ||
    extractError(summaryQuery.error);

  return (
    <section>
      <PageHeader
        eyebrow="Quick Play"
        title="Quick Play"
        subtitle="Pick provider and model, launch one game, and monitor board/replay without leaving this page."
      />

      <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <div className="grid gap-3 md:grid-cols-[1.2fr_1.2fr_auto]">
          <label className="text-xs text-[var(--color-text-secondary)]">
            Provider
            <select
              value={selectedProviderId}
              onChange={(event) => setSelectedProvider(normalizeProviderId(event.target.value))}
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
              disabled={modelCatalogQuery.isLoading || providerPresets.length === 0}
            >
              {providerPresets.map((preset) => {
                const providerId = normalizeProviderId(preset.provider);
                const providerReady = providerStatusMap.get(providerId) === true;
                return (
                  <option key={providerId} value={providerId}>
                    {preset.provider_label} {providerReady ? "(ready)" : "(missing key)"}
                  </option>
                );
              })}
            </select>
          </label>

          <label className="text-xs text-[var(--color-text-secondary)]">
            Model
            <select
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
              disabled={!activePreset}
            >
              {(activePreset?.models ?? []).map((model) => (
                <option key={model.id} value={model.id}>
                  {model.label}
                  {model.recommended ? " (Recommended)" : ""}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-end">
            <button
              type="button"
              onClick={() => {
                const payload = buildPlayPayload({
                  configPath: chosenConfigPath,
                  provider: selectedProviderId,
                  model: selectedModel,
                  boardFormat,
                  provideLegalMoves,
                  provideHistory,
                  feedbackLevel,
                  opponentMode,
                  stockfishLevel,
                  autoEvaluateEnabled: stockfishAvailable && autoEvaluateEnabled,
                  customOverrides: parsedCustomOverrides,
                });

                startPlayMutation.mutate(payload, {
                  onSuccess: handlePlayJobStarted,
                });
              }}
              disabled={!canStartGame}
              className="w-full rounded-lg border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-2 text-sm font-semibold text-[var(--color-surface-canvas)] md:w-auto"
            >
              {startPlayMutation.isPending ? "Starting..." : "Play Game"}
            </button>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <StatusBadge label={selectedProviderReady ? "provider ready" : "provider missing key"} tone={selectedProviderReady ? "success" : "error"} />
          <span className="text-[var(--color-text-secondary)]">Template: {chosenConfigPath}</span>
          {activePreset?.notes ? <span className="text-[var(--color-text-secondary)]">Notes: {activePreset.notes}</span> : null}
        </div>

        {showNoProviderConfigured ? (
          <div className="mt-3 rounded-xl border border-[var(--color-warning-border)] bg-[var(--color-warning-bg)] px-3 py-2 text-sm text-[var(--color-warning-text)]">
            No configured providers found. Add at least one API key in{" "}
            <Link to="/settings" className="font-semibold underline">
              Settings
            </Link>
            .
          </div>
        ) : null}

        <div className="mt-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2">
          <button
            type="button"
            onClick={() => setAdvancedOpen((prev) => !prev)}
            className="w-full text-left text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]"
          >
            {advancedOpen ? "Hide advanced options" : "Show advanced options"}
          </button>

          {advancedOpen ? (
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <label className="text-xs text-[var(--color-text-secondary)]">
                Board format
                <select
                  value={boardFormat}
                  onChange={(event) => setBoardFormat(event.target.value as BoardFormat)}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                >
                  <option value="fen">FEN</option>
                  <option value="pgn">PGN</option>
                </select>
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Feedback level
                <select
                  value={feedbackLevel}
                  onChange={(event) => setFeedbackLevel(event.target.value as FeedbackLevel)}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                >
                  <option value="minimal">minimal</option>
                  <option value="moderate">moderate</option>
                  <option value="rich">rich</option>
                </select>
              </label>

              <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-primary)]">
                <input
                  type="checkbox"
                  checked={provideLegalMoves}
                  onChange={(event) => setProvideLegalMoves(event.target.checked)}
                  className="h-4 w-4 rounded border-[var(--color-border-strong)]"
                />
                Include legal moves in prompt
              </label>

              <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-primary)]">
                <input
                  type="checkbox"
                  checked={provideHistory}
                  onChange={(event) => setProvideHistory(event.target.checked)}
                  className="h-4 w-4 rounded border-[var(--color-border-strong)]"
                />
                Include move history
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Opponent
                <select
                  value={opponentMode}
                  onChange={(event) => setOpponentMode(event.target.value as OpponentMode)}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                >
                  <option value="random">Random</option>
                  <option value="stockfish">Stockfish</option>
                </select>
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Stockfish level/depth
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={stockfishLevel}
                  onChange={(event) => setStockfishLevel(clampInt(event.target.value, 1, 20, 8))}
                  disabled={opponentMode !== "stockfish"}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                />
              </label>

              <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-primary)] md:col-span-2">
                <input
                  type="checkbox"
                  checked={autoEvaluateEnabled}
                  onChange={(event) => {
                    setAutoEvaluateEnabled(event.target.checked);
                    setAutoEvaluatePreference(event.target.checked);
                  }}
                  disabled={!stockfishAvailable}
                  className="h-4 w-4 rounded border-[var(--color-border-strong)]"
                />
                Auto-evaluate after play
              </label>

              <label className="text-xs text-[var(--color-text-secondary)] md:col-span-2">
                Raw overrides (`key=value`, one per line)
                <textarea
                  value={rawOverridesText}
                  onChange={(event) => setRawOverridesText(event.target.value)}
                  rows={5}
                  placeholder="players.white.name=my_opponent"
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 font-['IBM_Plex_Mono'] text-xs text-[var(--color-text-primary)]"
                />
              </label>

              {!stockfishAvailable ? (
                <p className="text-xs text-[var(--color-warning-text)] md:col-span-2">Stockfish unavailable. Auto-eval toggle is disabled.</p>
              ) : null}
            </div>
          ) : null}
        </div>

        {invalidOverrideLines.length > 0 ? (
          <div className="mt-3 rounded-xl border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-3 py-2 text-sm text-[var(--color-error-text)]">
            Invalid override lines: {invalidOverrideLines.join(", ")}
          </div>
        ) : null}
      </section>

      <section className="mt-5 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Live game</p>
          {isRunning ? <StatusBadge label="thinking..." tone="info" /> : null}
          {isTerminal ? <StatusBadge label={activeJobStatus ?? "completed"} tone={activeJobStatus === "completed" ? "success" : "warning"} /> : null}
        </div>

        {!activeJobId ? (
          <p className="text-sm text-[var(--color-text-secondary)]">Press Play Game to start a one-game session.</p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[430px_1fr]">
            <article className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
              <div className="mx-auto w-full max-w-[400px]">
                <Chessboard
                  options={{
                    id: "quick-play-board",
                    position: latestFen,
                    boardOrientation: "white",
                    allowDragging: false,
                    allowDrawingArrows: true,
                    arrows: boardArrow ? [boardArrow] : [],
                    boardStyle: { width: "100%", maxWidth: "400px" },
                    darkSquareStyle: { backgroundColor: "#c4a877" },
                    lightSquareStyle: { backgroundColor: "#f2dfbf" },
                  }}
                />
              </div>
            </article>

            <article className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <MetricChip label="Run ID" value={runId ?? "--"} />
                <MetricChip label="Job ID" value={activeJobId} />
                <MetricChip label="Tokens used" value={totalTokens > 0 ? String(totalTokens) : "--"} />
                <MetricChip label="Cost USD" value={formatUsd(totalCost, 6)} />
              </div>

              <div className="mt-3">
                <ProgressBar
                  value={progressQuery.data?.games_written ?? 0}
                  max={Math.max(1, progressQuery.data?.games_target ?? 1)}
                  label={`${progressQuery.data?.games_written ?? 0}/${progressQuery.data?.games_target ?? 1} games`}
                />
              </div>

              <div className="mt-3">
                <p className="mb-1 text-xs uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Moves</p>
                {moveRows.length === 0 ? (
                  <p className="text-sm text-[var(--color-text-secondary)]">{isRunning ? "Waiting for first move..." : "No move records yet."}</p>
                ) : (
                  <div className="max-h-[220px] overflow-auto rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-raised)] p-2">
                    <ol className="space-y-1 text-sm text-[var(--color-text-primary)]">
                      {moveRows.map((move) => (
                        <li key={move.key} className="font-mono text-xs">
                          {move.ply}. {move.label}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            </article>
          </div>
        )}
      </section>

      {isTerminal && gameQuery.data ? (
        <section className="mt-5 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Result summary</p>
          <p className="mt-2 text-sm text-[var(--color-text-primary)]">
            {resultLabel} ({resultTermination}) | {resultMoves} moves | {resultDuration ? `${resultDuration.toFixed(1)}s` : "--"} | {formatUsd(totalCost, 6)}
          </p>

          {summaryQuery.data?.evaluated_report ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              <MetricChip label="ACPL" value={formatDecimal(summaryMetrics.acplOverall, 1)} />
              <MetricChip label="Blunder rate" value={formatRate(summaryMetrics.blunderRate, 1)} />
              <MetricChip label="Best move agreement" value={formatRate(summaryMetrics.bestMoveAgreement, 1)} />
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2">
            {runId ? (
              <Link
                to="/runs/$runId"
                params={{ runId }}
                className="rounded-lg border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-2 text-sm font-semibold text-[var(--color-surface-canvas)]"
              >
                View Full Analysis
              </Link>
            ) : null}

            <button
              type="button"
              className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm font-semibold text-[var(--color-text-primary)]"
              onClick={() => {
                const payload = buildPlayPayload({
                  configPath: chosenConfigPath,
                  provider: selectedProviderId,
                  model: selectedModel,
                  boardFormat,
                  provideLegalMoves,
                  provideHistory,
                  feedbackLevel,
                  opponentMode,
                  stockfishLevel,
                  autoEvaluateEnabled: stockfishAvailable && autoEvaluateEnabled,
                  customOverrides: parsedCustomOverrides,
                });

                startPlayMutation.mutate(payload, {
                  onSuccess: handlePlayJobStarted,
                });
              }}
              disabled={!canStartGame}
            >
              Play Again
            </button>

            <button
              type="button"
              className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm font-semibold text-[var(--color-text-primary)]"
              onClick={() => {
                const labOverrides = buildPlayPayload({
                  configPath: chosenConfigPath,
                  provider: selectedProviderId,
                  model: selectedModel,
                  boardFormat,
                  provideLegalMoves,
                  provideHistory,
                  feedbackLevel,
                  opponentMode,
                  stockfishLevel,
                  autoEvaluateEnabled: stockfishAvailable && autoEvaluateEnabled,
                  customOverrides: parsedCustomOverrides,
                  includeSeedOverride: false,
                }).overrides ?? [];

                setLabTemplatePath(chosenConfigPath);
                setLabProvider(selectedProviderId || null);
                setLabModel(selectedModel || null);
                setLabOverrides(labOverrides.join("\n"));
                setLabAdvancedOpen(true);
                navigate({ to: "/lab" });
              }}
            >
              Open in Lab
            </button>
          </div>
        </section>
      ) : null}

      {statusError ? (
        <div className="mt-5 rounded-xl border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-4 py-3 text-sm text-[var(--color-error-text)]">
          {statusError}
        </div>
      ) : null}

      {hasLiveData && isRunning ? (
        <p className="mt-3 text-xs text-[var(--color-text-secondary)]">Live view updates every 2 seconds while the game is running.</p>
      ) : null}
    </section>
  );

  function handlePlayJobStarted(job: JobResponse): void {
    setActiveJobId(job.job_id);
    setActiveRunId(job.run_id ?? null);
    setRunArtifactsReadyAt(Date.now() + RUN_ARTIFACTS_BOOTSTRAP_DELAY_MS);
  }
}

function buildPlayPayload(input: {
  configPath: string;
  provider: string;
  model: string;
  boardFormat: BoardFormat;
  provideLegalMoves: boolean;
  provideHistory: boolean;
  feedbackLevel: FeedbackLevel;
  opponentMode: OpponentMode;
  stockfishLevel: number;
  autoEvaluateEnabled: boolean;
  customOverrides: string[];
  includeSeedOverride?: boolean;
}): StartJobRequest {
  const overrides = [
    `players.black.type=llm`,
    `players.black.provider=${input.provider}`,
    `players.black.model=${input.model}`,
    `players.black.name=${safeModelName(input.provider, input.model)}`,
    `strategy.board_format=${input.boardFormat}`,
    `strategy.provide_legal_moves=${input.provideLegalMoves}`,
    `strategy.provide_history=${input.provideHistory}`,
    `strategy.validation.feedback_level=${input.feedbackLevel}`,
  ];

  if (input.opponentMode === "stockfish") {
    overrides.push("players.white.type=engine");
    overrides.push("players.white.name=stockfish_white");
    overrides.push(`players.white.depth=${input.stockfishLevel}`);
  } else {
    overrides.push("players.white.type=random");
    overrides.push("players.white.name=random_white");
  }

  if (input.autoEvaluateEnabled) {
    overrides.push("evaluation.auto.enabled=true");
    overrides.push("evaluation.auto.player_color=black");
    if (input.opponentMode === "stockfish") {
      overrides.push(`evaluation.auto.opponent_elo=${mapStockfishLevelToElo(input.stockfishLevel)}`);
    }
  } else {
    overrides.push("evaluation.auto.enabled=false");
  }

  if (input.includeSeedOverride !== false) {
    overrides.push(`runtime.seed=${Math.floor(Date.now() % 2_000_000_000)}`);
  }

  return {
    config_path: input.configPath,
    model_profile: null,
    overrides: [...overrides, ...input.customOverrides],
  };
}

function normalizeProviderId(value: string | null | undefined): string {
  const normalized = (value ?? "").trim().toLowerCase();
  if (normalized === "z.ai") {
    return "zai";
  }
  return normalized;
}

function parseOverrides(raw: string): string[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));
}

function safeModelName(provider: string, model: string): string {
  return `${provider}_${model}`.replace(/[^a-zA-Z0-9_-]+/g, "_");
}

function mapStockfishLevelToElo(level: number): number {
  if (level <= 2) {
    return 600;
  }
  if (level <= 5) {
    return 800;
  }
  if (level <= 8) {
    return 1000;
  }
  if (level <= 11) {
    return 1200;
  }
  if (level <= 14) {
    return 1600;
  }
  if (level <= 17) {
    return 2000;
  }
  return 2500;
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

function loadAdvancedOpen(): boolean {
  try {
    return window.sessionStorage.getItem(ADVANCED_OPEN_SESSION_KEY) === "true";
  } catch {
    return false;
  }
}

function persistAdvancedOpen(value: boolean): void {
  try {
    window.sessionStorage.setItem(ADVANCED_OPEN_SESSION_KEY, value ? "true" : "false");
  } catch {
    // ignore storage unavailability
  }
}

function isTerminalStatus(status: string | null | undefined): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}

function shouldRetryWithout404(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status === 404) {
    return false;
  }
  return failureCount < 2;
}

function clampInt(raw: string, minimum: number, maximum: number, fallback: number): number {
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(minimum, Math.min(maximum, parsed));
}

function extractError(error: unknown): string | null {
  if (!error) {
    return null;
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function extractRunArtifactError(error: unknown, isRunning: boolean): string | null {
  if (isRunning && isNotFoundError(error)) {
    return null;
  }
  return extractError(error);
}

function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
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

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-surface-raised)] px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-1 truncate text-xs font-semibold text-[var(--color-text-primary)]">{value}</p>
    </div>
  );
}
