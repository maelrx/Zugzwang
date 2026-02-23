import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import {
  useConfigs,
  useEnvCheck,
  useModelCatalog,
  usePreviewConfig,
  useStartPlay,
  useStartRun,
  useValidateConfig,
} from "../../api/queries";
import { useLabStore } from "../../stores/labStore";
import { usePreferencesStore } from "../../stores/preferencesStore";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatUsd } from "../lib/runMetrics";

const AUTO_CHECK_DEBOUNCE_MS = 500;
const MIN_TARGET_GAMES = 1;
const MAX_TARGET_GAMES = 500;
const DEFAULT_TARGET_GAMES = 10;

type TemplateBucket = "baselines" | "ablations" | "custom";
type BoardFormat = "fen" | "pgn";
type FeedbackLevel = "minimal" | "moderate" | "rich";
type OpponentMode = "template" | "random" | "stockfish" | "llm";

type TemplateOption = {
  name: string;
  path: string;
  category: string;
  bucket: TemplateBucket;
};

export function RunLabPage() {
  const navigate = useNavigate();
  const configsQuery = useConfigs();
  const modelCatalogQuery = useModelCatalog();
  const envCheckQuery = useEnvCheck();
  const validateMutation = useValidateConfig();
  const previewMutation = usePreviewConfig();
  const startRunMutation = useStartRun();
  const startPlayMutation = useStartPlay();

  const storedTemplatePath = useLabStore((state) => state.selectedTemplatePath);
  const storedProvider = useLabStore((state) => state.selectedProvider);
  const storedModel = useLabStore((state) => state.selectedModel);
  const storedOverrides = useLabStore((state) => state.rawOverridesText);
  const storedAdvancedOpen = useLabStore((state) => state.advancedOpen);
  const setStoredTemplatePath = useLabStore((state) => state.setSelectedTemplatePath);
  const setStoredProvider = useLabStore((state) => state.setSelectedProvider);
  const setStoredModel = useLabStore((state) => state.setSelectedModel);
  const setStoredOverrides = useLabStore((state) => state.setRawOverridesText);
  const setStoredAdvancedOpen = useLabStore((state) => state.setAdvancedOpen);

  const autoEvaluatePreference = usePreferencesStore((state) => state.autoEvaluate);
  const defaultProvider = usePreferencesStore((state) => state.defaultProvider);
  const defaultModel = usePreferencesStore((state) => state.defaultModel);
  const stockfishDepthPreference = usePreferencesStore((state) => state.stockfishDepth);
  const setAutoEvaluatePreference = usePreferencesStore((state) => state.setAutoEvaluate);
  const setStockfishDepthPreference = usePreferencesStore((state) => state.setStockfishDepth);

  const [templateSearch, setTemplateSearch] = useState("");
  const [selectedConfigPath, setSelectedConfigPath] = useState(storedTemplatePath ?? "");
  const [selectedProvider, setSelectedProvider] = useState(storedProvider ?? "");
  const [selectedModel, setSelectedModel] = useState(storedModel ?? "");
  const [modelProfile, setModelProfile] = useState("");
  const [targetValidGames, setTargetValidGames] = useState(DEFAULT_TARGET_GAMES);
  const [maxBudgetUsdText, setMaxBudgetUsdText] = useState("");
  const [boardFormat, setBoardFormat] = useState<BoardFormat>("fen");
  const [provideLegalMoves, setProvideLegalMoves] = useState(true);
  const [provideHistory, setProvideHistory] = useState(true);
  const [feedbackLevel, setFeedbackLevel] = useState<FeedbackLevel>("rich");
  const [opponentMode, setOpponentMode] = useState<OpponentMode>("template");
  const [opponentProvider, setOpponentProvider] = useState(storedProvider ?? defaultProvider ?? "");
  const [opponentModel, setOpponentModel] = useState(storedModel ?? defaultModel ?? "");
  const [opponentStockfishLevel, setOpponentStockfishLevel] = useState(stockfishDepthPreference);
  const [autoEvaluateEnabled, setAutoEvaluateEnabled] = useState(autoEvaluatePreference);
  const [evaluationPlayerColor, setEvaluationPlayerColor] = useState<"white" | "black">("black");
  const [evaluationOpponentEloText, setEvaluationOpponentEloText] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(storedAdvancedOpen);
  const [customOverridesText, setCustomOverridesText] = useState(storedOverrides);

  const templates = useMemo(() => {
    const all = [...(configsQuery.data?.baselines ?? []), ...(configsQuery.data?.ablations ?? [])];
    return all.map<TemplateOption>((template) => ({
      name: template.name,
      path: template.path,
      category: template.category,
      bucket: resolveTemplateBucket(template.category, template.path),
    }));
  }, [configsQuery.data?.ablations, configsQuery.data?.baselines]);

  const filteredTemplates = useMemo(() => {
    const query = templateSearch.trim().toLowerCase();
    if (!query) {
      return templates;
    }
    return templates.filter((item) => item.name.toLowerCase().includes(query) || item.path.toLowerCase().includes(query));
  }, [templateSearch, templates]);

  const groupedTemplates = useMemo(
    () => ({
      baselines: filteredTemplates.filter((item) => item.bucket === "baselines"),
      ablations: filteredTemplates.filter((item) => item.bucket === "ablations"),
      custom: filteredTemplates.filter((item) => item.bucket === "custom"),
    }),
    [filteredTemplates],
  );

  const currentConfigPath = selectedConfigPath || templates[0]?.path || "";
  const selectedTemplate = useMemo(
    () => templates.find((item) => item.path === currentConfigPath) ?? null,
    [currentConfigPath, templates],
  );

  const providerPresets = modelCatalogQuery.data ?? [];
  const envChecks = envCheckQuery.data ?? [];
  const providerStatusMap = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const item of envChecks) {
      map.set(item.provider, item.ok);
    }
    return map;
  }, [envChecks]);
  const stockfishCheckKnown = useMemo(() => envChecks.some((item) => item.provider === "stockfish"), [envChecks]);
  const stockfishAvailable = providerStatusMap.get("stockfish") === true;
  const selectedProviderReady = providerStatusMap.get(selectedProvider) === true;
  const opponentProviderReady = providerStatusMap.get(opponentProvider) === true;

  const activePreset = useMemo(
    () => providerPresets.find((preset) => preset.provider === selectedProvider) ?? null,
    [providerPresets, selectedProvider],
  );
  const opponentPreset = useMemo(
    () => providerPresets.find((preset) => preset.provider === opponentProvider) ?? null,
    [opponentProvider, providerPresets],
  );

  const parsedCustomOverrides = useMemo(() => parseOverrides(customOverridesText), [customOverridesText]);
  const invalidOverrideLines = useMemo(
    () => parsedCustomOverrides.filter((line) => !line.includes("=")),
    [parsedCustomOverrides],
  );
  const validCustomOverrides = useMemo(
    () => parsedCustomOverrides.filter((line) => line.includes("=")),
    [parsedCustomOverrides],
  );

  const parsedMaxBudgetUsd = parseOptionalPositiveNumber(maxBudgetUsdText);
  const invalidMaxBudgetUsd = maxBudgetUsdText.trim().length > 0 && parsedMaxBudgetUsd === null;
  const parsedOpponentElo = parseOptionalInteger(evaluationOpponentEloText);
  const invalidOpponentElo = evaluationOpponentEloText.trim().length > 0 && parsedOpponentElo === null;

  const structuredOverrides = useMemo(
    () =>
      buildStructuredOverrides({
        provider: selectedProvider,
        model: selectedModel,
        opponentMode,
        opponentProvider,
        opponentModel,
        opponentStockfishLevel,
        targetValidGames,
        maxBudgetUsd: parsedMaxBudgetUsd,
        boardFormat,
        provideLegalMoves,
        provideHistory,
        feedbackLevel,
        autoEvaluateEnabled,
        evaluationPlayerColor,
        evaluationOpponentElo: parsedOpponentElo,
      }),
    [
      autoEvaluateEnabled,
      boardFormat,
      evaluationPlayerColor,
      feedbackLevel,
      parsedMaxBudgetUsd,
      parsedOpponentElo,
      opponentMode,
      opponentModel,
      opponentProvider,
      opponentStockfishLevel,
      provideHistory,
      provideLegalMoves,
      selectedModel,
      selectedProvider,
      targetValidGames,
    ],
  );

  const mergedOverrides = useMemo(
    () => mergeOverrides(structuredOverrides, validCustomOverrides),
    [structuredOverrides, validCustomOverrides],
  );

  const requestPayload = useMemo(
    () => ({
      config_path: currentConfigPath,
      model_profile: modelProfile.trim() || null,
      overrides: mergedOverrides,
    }),
    [currentConfigPath, mergedOverrides, modelProfile],
  );
  const requestPayloadSignature = useMemo(() => JSON.stringify(requestPayload), [requestPayload]);
  const lastAutoCheckedSignatureRef = useRef<string | null>(null);
  const triggerValidate = validateMutation.mutate;
  const triggerPreview = previewMutation.mutate;

  const isLaunching = startRunMutation.isPending || startPlayMutation.isPending;
  const canAutoCheck =
    Boolean(currentConfigPath) &&
    Boolean(selectedProvider) &&
    Boolean(selectedModel) &&
    (opponentMode !== "llm" || (Boolean(opponentProvider) && Boolean(opponentModel))) &&
    (opponentMode !== "stockfish" || stockfishAvailable) &&
    invalidOverrideLines.length === 0 &&
    !invalidMaxBudgetUsd &&
    !invalidOpponentElo;

  useEffect(() => {
    if (templates.length === 0) {
      return;
    }
    if (!selectedConfigPath || !templates.some((item) => item.path === selectedConfigPath)) {
      setSelectedConfigPath(templates[0]?.path ?? "");
    }
  }, [selectedConfigPath, templates]);

  useEffect(() => {
    if (selectedProvider && providerPresets.some((preset) => preset.provider === selectedProvider)) {
      return;
    }
    const preferred = defaultProvider ? providerPresets.find((preset) => preset.provider === defaultProvider) : undefined;
    setSelectedProvider(preferred?.provider ?? providerPresets[0]?.provider ?? "");
  }, [defaultProvider, providerPresets, selectedProvider]);

  useEffect(() => {
    if (!activePreset) {
      setSelectedModel("");
      return;
    }
    if (activePreset.models.some((item) => item.id === selectedModel)) {
      return;
    }
    const preferredModel = defaultModel ? activePreset.models.find((item) => item.id === defaultModel) : undefined;
    const fallback = preferredModel ?? activePreset.models.find((item) => item.recommended) ?? activePreset.models[0] ?? null;
    setSelectedModel(fallback?.id ?? "");
  }, [activePreset, defaultModel, selectedModel]);

  useEffect(() => {
    if (providerPresets.length === 0 || opponentMode !== "llm") {
      return;
    }
    if (opponentProvider && providerPresets.some((preset) => preset.provider === opponentProvider)) {
      return;
    }
    setOpponentProvider(selectedProvider || (providerPresets[0]?.provider ?? ""));
  }, [opponentMode, opponentProvider, providerPresets, selectedProvider]);

  useEffect(() => {
    if (!opponentPreset || opponentMode !== "llm") {
      setOpponentModel("");
      return;
    }
    if (opponentPreset.models.some((item) => item.id === opponentModel)) {
      return;
    }
    const mirrorModel = selectedModel ? opponentPreset.models.find((item) => item.id === selectedModel) : undefined;
    const fallback = mirrorModel ?? opponentPreset.models.find((item) => item.recommended) ?? opponentPreset.models[0] ?? null;
    setOpponentModel(fallback?.id ?? "");
  }, [opponentMode, opponentModel, opponentPreset, selectedModel]);

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
    if (stockfishDepthPreference !== opponentStockfishLevel) {
      setOpponentStockfishLevel(stockfishDepthPreference);
    }
  }, [opponentStockfishLevel, stockfishDepthPreference]);

  useEffect(() => {
    setStoredTemplatePath(selectedConfigPath || null);
  }, [selectedConfigPath, setStoredTemplatePath]);

  useEffect(() => {
    setStoredProvider(selectedProvider || null);
  }, [selectedProvider, setStoredProvider]);

  useEffect(() => {
    setStoredModel(selectedModel || null);
  }, [selectedModel, setStoredModel]);

  useEffect(() => {
    setStoredOverrides(customOverridesText);
  }, [customOverridesText, setStoredOverrides]);

  useEffect(() => {
    setStoredAdvancedOpen(advancedOpen);
  }, [advancedOpen, setStoredAdvancedOpen]);

  useEffect(() => {
    if (!canAutoCheck) {
      lastAutoCheckedSignatureRef.current = null;
      return;
    }
    if (requestPayloadSignature === lastAutoCheckedSignatureRef.current) {
      return;
    }
    const timeout = window.setTimeout(() => {
      lastAutoCheckedSignatureRef.current = requestPayloadSignature;
      triggerValidate(requestPayload);
      triggerPreview(requestPayload);
    }, AUTO_CHECK_DEBOUNCE_MS);
    return () => window.clearTimeout(timeout);
  }, [canAutoCheck, requestPayload, requestPayloadSignature, triggerPreview, triggerValidate]);

  const blockingErrors = useMemo(() => {
    const errors: string[] = [];
    if (!currentConfigPath) {
      errors.push("Select a template.");
    }
    if (!selectedProvider || !selectedModel) {
      errors.push("Select provider and model.");
    }
    if (opponentMode === "llm" && (!opponentProvider || !opponentModel)) {
      errors.push("Select opponent provider and model.");
    }
    if (invalidOverrideLines.length > 0) {
      errors.push(`Fix invalid override lines: ${invalidOverrideLines.join(", ")}`);
    }
    if (invalidMaxBudgetUsd) {
      errors.push("Max budget must be a positive number.");
    }
    if (invalidOpponentElo) {
      errors.push("Opponent Elo must be an integer.");
    }
    if (envCheckQuery.isSuccess && selectedProvider && !selectedProviderReady) {
      errors.push(`Provider "${selectedProvider}" is missing credentials in Settings.`);
    }
    if (envCheckQuery.isSuccess && opponentMode === "llm" && opponentProvider && !opponentProviderReady) {
      errors.push(`Opponent provider "${opponentProvider}" is missing credentials in Settings.`);
    }
    if (envCheckQuery.isSuccess && opponentMode === "stockfish" && stockfishCheckKnown && !stockfishAvailable) {
      errors.push("Stockfish opponent selected but Stockfish is unavailable.");
    }
    if (autoEvaluateEnabled && envCheckQuery.isSuccess && stockfishCheckKnown && !stockfishAvailable) {
      errors.push("Auto-evaluate is enabled but Stockfish is unavailable.");
    }
    if (validateMutation.data && !validateMutation.data.ok) {
      errors.push(validateMutation.data.message || "Config validation failed.");
    }
    if (validateMutation.isError) {
      errors.push(extractErrorMessage(validateMutation.error));
    }
    if (previewMutation.isError) {
      errors.push(extractErrorMessage(previewMutation.error));
    }
    return dedupeStrings(errors).filter((item) => item.trim().length > 0);
  }, [
    autoEvaluateEnabled,
    currentConfigPath,
    envCheckQuery.isSuccess,
    invalidMaxBudgetUsd,
    invalidOpponentElo,
    invalidOverrideLines,
    opponentMode,
    opponentModel,
    opponentProvider,
    opponentProviderReady,
    previewMutation.error,
    previewMutation.isError,
    selectedModel,
    selectedProvider,
    selectedProviderReady,
    stockfishAvailable,
    stockfishCheckKnown,
    validateMutation.data,
    validateMutation.error,
    validateMutation.isError,
  ]);

  const canLaunch = canAutoCheck && blockingErrors.length === 0 && !isLaunching && !validateMutation.isPending && !previewMutation.isPending;
  const previewData = previewMutation.data;
  const resolvedConfigPreview = previewData?.resolved_config ?? validateMutation.data?.resolved_config ?? null;
  const estimatedCostUsd = previewData?.estimated_total_cost_usd ?? null;

  const baselineCount = templates.filter((item) => item.bucket === "baselines").length;
  const ablationCount = templates.filter((item) => item.bucket === "ablations").length;
  const customCount = templates.filter((item) => item.bucket === "custom").length;

  return (
    <section>
      <PageHeader
        eyebrow="Run Lab"
        title="Experiment Launch Workbench"
        subtitle="Build, validate and launch multi-game experiments with live preview and safety checks."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
        <StatusBadge label={selectedProviderReady ? "provider ready" : "provider missing key"} tone={selectedProviderReady ? "success" : "error"} />
        <StatusBadge label={stockfishAvailable ? "stockfish ready" : "stockfish missing"} tone={stockfishAvailable ? "success" : "warning"} />
        <span className="text-[var(--color-text-secondary)]">
          Templates: {configsQuery.isLoading ? "..." : `${baselineCount} baselines / ${ablationCount} ablations / ${customCount} custom`}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)_minmax(0,1fr)]">
        <section className="min-w-0 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Template Browser</p>
          <label className="mt-2 block text-xs text-[var(--color-text-secondary)]">
            Search templates
            <input
              value={templateSearch}
              onChange={(event) => setTemplateSearch(event.target.value)}
              placeholder="best_known_start..."
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            />
          </label>

          <div className="mt-3 max-h-[620px] overflow-auto pr-1">
            <TemplateGroup
              label="Baselines"
              templates={groupedTemplates.baselines}
              selectedPath={currentConfigPath}
              onSelect={setSelectedConfigPath}
            />
            <TemplateGroup
              label="Ablations"
              templates={groupedTemplates.ablations}
              selectedPath={currentConfigPath}
              onSelect={setSelectedConfigPath}
            />
            <TemplateGroup label="Custom" templates={groupedTemplates.custom} selectedPath={currentConfigPath} onSelect={setSelectedConfigPath} />

            {filteredTemplates.length === 0 ? (
              <p className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2 text-xs text-[var(--color-text-secondary)]">
                No templates match this search.
              </p>
            ) : null}
          </div>
        </section>

        <section className="min-w-0 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Config Builder</p>
              <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Structured inputs generate deterministic overrides for this template.</p>
            </div>
            <StatusBadge label={selectedTemplate ? selectedTemplate.bucket : "unselected"} tone="info" />
          </div>

          <div className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Model</p>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="text-xs text-[var(--color-text-secondary)]">
                Provider
                <select
                  value={selectedProvider}
                  onChange={(event) => setSelectedProvider(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                >
                  {providerPresets.map((preset) => (
                    <option key={preset.provider} value={preset.provider}>
                      {preset.provider_label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Model
                <select
                  value={selectedModel}
                  onChange={(event) => setSelectedModel(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
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
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="rounded-md border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-1.5 text-xs font-semibold text-[var(--color-surface-canvas)]"
                disabled={!selectedProvider || !selectedModel}
                onClick={() => {
                  setCustomOverridesText((prev) =>
                    upsertOverrides(prev, {
                      "players.black.type": "llm",
                      "players.black.provider": selectedProvider,
                      "players.black.model": selectedModel,
                      "players.black.name": safeModelName(selectedProvider, selectedModel),
                    }),
                  );
                }}
              >
                Apply Preset to Overrides
              </button>
              {opponentMode === "llm" ? (
                <button
                  type="button"
                  className="rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface-raised)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-primary)]"
                  disabled={!selectedProvider || !selectedModel}
                  onClick={() => {
                    setOpponentProvider(selectedProvider);
                    setOpponentModel(selectedModel);
                  }}
                >
                  Mirror as Opponent
                </button>
              ) : null}
              {activePreset ? (
                <p className="text-[11px] text-[var(--color-text-secondary)]">
                  {activePreset.api_style} | {activePreset.base_url}
                </p>
              ) : null}
            </div>
          </div>
          <details className="mt-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3" open>
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Experiment</summary>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="text-xs text-[var(--color-text-secondary)]">
                Target valid games
                <input
                  type="number"
                  min={MIN_TARGET_GAMES}
                  max={MAX_TARGET_GAMES}
                  value={targetValidGames}
                  onChange={(event) => setTargetValidGames(clampInt(event.target.value, MIN_TARGET_GAMES, MAX_TARGET_GAMES, DEFAULT_TARGET_GAMES))}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                />
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Max budget USD (optional)
                <input
                  value={maxBudgetUsdText}
                  onChange={(event) => setMaxBudgetUsdText(event.target.value)}
                  placeholder="e.g. 2.50"
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                />
              </label>
            </div>
          </details>

          <details className="mt-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3" open>
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Opponent</summary>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="text-xs text-[var(--color-text-secondary)]">
                Opponent mode
                <select
                  value={opponentMode}
                  onChange={(event) => setOpponentMode(event.target.value as OpponentMode)}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                >
                  <option value="template">Template default</option>
                  <option value="random">Random</option>
                  <option value="stockfish">Stockfish</option>
                  <option value="llm">LLM</option>
                </select>
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Stockfish depth
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={opponentStockfishLevel}
                  onChange={(event) => {
                    const level = clampInt(event.target.value, 1, 20, 8);
                    setOpponentStockfishLevel(level);
                    setStockfishDepthPreference(level);
                  }}
                  disabled={opponentMode !== "stockfish" || !stockfishAvailable}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                />
              </label>

              {opponentMode === "llm" ? (
                <>
                  <label className="text-xs text-[var(--color-text-secondary)]">
                    Opponent provider
                    <select
                      value={opponentProvider}
                      onChange={(event) => setOpponentProvider(event.target.value)}
                      className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                    >
                      {providerPresets.map((preset) => (
                        <option key={`opponent-${preset.provider}`} value={preset.provider}>
                          {preset.provider_label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="text-xs text-[var(--color-text-secondary)]">
                    Opponent model
                    <select
                      value={opponentModel}
                      onChange={(event) => setOpponentModel(event.target.value)}
                      className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                      disabled={!opponentPreset}
                    >
                      {(opponentPreset?.models ?? []).map((model) => (
                        <option key={`opponent-model-${model.id}`} value={model.id}>
                          {model.label}
                          {model.recommended ? " (Recommended)" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              ) : null}
            </div>

            {opponentMode === "stockfish" && !stockfishAvailable ? (
              <p className="mt-2 text-xs text-[var(--color-warning-text)]">
                Stockfish opponent requires STOCKFISH_PATH in{" "}
                <Link to="/settings" className="underline">
                  Settings
                </Link>
                .
              </p>
            ) : null}
            {opponentMode === "llm" && opponentProvider && !opponentProviderReady ? (
              <p className="mt-2 text-xs text-[var(--color-warning-text)]">
                Opponent provider credentials missing in{" "}
                <Link to="/settings" className="underline">
                  Settings
                </Link>
                .
              </p>
            ) : null}
          </details>

          <details className="mt-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3" open>
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Strategy</summary>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="text-xs text-[var(--color-text-secondary)]">
                Board format
                <select
                  value={boardFormat}
                  onChange={(event) => setBoardFormat(event.target.value as BoardFormat)}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                >
                  <option value="fen">fen</option>
                  <option value="pgn">pgn</option>
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
            </div>

            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-primary)]">
                <input
                  type="checkbox"
                  checked={provideLegalMoves}
                  onChange={(event) => setProvideLegalMoves(event.target.checked)}
                  className="h-4 w-4 rounded border-[var(--color-border-strong)]"
                />
                Include legal moves
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-primary)]">
                <input
                  type="checkbox"
                  checked={provideHistory}
                  onChange={(event) => setProvideHistory(event.target.checked)}
                  className="h-4 w-4 rounded border-[var(--color-border-strong)]"
                />
                Include history
              </label>
            </div>
          </details>

          <details className="mt-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3" open>
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
              Evaluation Settings
            </summary>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-primary)] sm:col-span-2">
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
                Auto-evaluate after run
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Player color
                <select
                  value={evaluationPlayerColor}
                  onChange={(event) => setEvaluationPlayerColor(event.target.value as "white" | "black")}
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                >
                  <option value="white">white</option>
                  <option value="black">black</option>
                </select>
              </label>

              <label className="text-xs text-[var(--color-text-secondary)]">
                Opponent Elo (optional)
                <input
                  value={evaluationOpponentEloText}
                  onChange={(event) => setEvaluationOpponentEloText(event.target.value)}
                  placeholder="e.g. 1000"
                  className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                />
              </label>
            </div>

            {!stockfishAvailable ? (
              <p className="mt-2 text-xs text-[var(--color-warning-text)]">
                Stockfish not detected. Configure it in{" "}
                <Link to="/settings" className="underline">
                  Settings
                </Link>{" "}
                to enable auto-evaluation.
              </p>
            ) : null}
          </details>

          <div className="mt-3 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
            <button
              type="button"
              onClick={() => setAdvancedOpen((prev) => !prev)}
              className="w-full text-left text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]"
            >
              {advancedOpen ? "Hide advanced overrides" : "Show advanced overrides"}
            </button>
            {advancedOpen ? (
              <div className="mt-3">
                <label className="block text-xs text-[var(--color-text-secondary)]">
                  Model profile (optional)
                  <input
                    value={modelProfile}
                    onChange={(event) => setModelProfile(event.target.value)}
                    placeholder="configs/models/..."
                    className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
                  />
                </label>

                <label className="mt-3 block text-xs text-[var(--color-text-secondary)]">
                  Overrides (`key=value`, one per line)
                  <textarea
                    value={customOverridesText}
                    onChange={(event) => setCustomOverridesText(event.target.value)}
                    rows={7}
                    placeholder="players.white.type=engine"
                    className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2.5 py-2 font-['IBM_Plex_Mono'] text-xs text-[var(--color-text-primary)]"
                  />
                </label>
              </div>
            ) : null}
          </div>
        </section>

        <section className="min-w-0 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Preview & Validation</p>
              <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                Auto-refreshes after changes ({AUTO_CHECK_DEBOUNCE_MS}ms debounce).
              </p>
            </div>
            <button
              type="button"
              className="rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-2.5 py-1 text-xs font-semibold text-[var(--color-text-primary)]"
              disabled={!canAutoCheck}
              onClick={() => {
                if (!canAutoCheck) {
                  return;
                }
                lastAutoCheckedSignatureRef.current = requestPayloadSignature;
                triggerValidate(requestPayload);
                triggerPreview(requestPayload);
              }}
            >
              Refresh
            </button>
          </div>

          <div className="space-y-2 rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3">
            <ChecklistRow
              label="Config valid"
              tone={
                validateMutation.isPending
                  ? "pending"
                  : validateMutation.data?.ok
                    ? "success"
                    : validateMutation.data
                      ? "error"
                      : "pending"
              }
              detail={validateMutation.data?.message ?? "Waiting for auto validation"}
            />
            <ChecklistRow
              label="Provider reachable"
              tone={
                !selectedProvider
                  ? "pending"
                  : envCheckQuery.isLoading
                    ? "pending"
                    : selectedProviderReady
                      ? "success"
                      : "error"
              }
              detail={selectedProvider || "Unselected"}
            />
            <ChecklistRow
              label="Stockfish for eval"
              tone={!autoEvaluateEnabled ? "warning" : stockfishAvailable ? "success" : envCheckQuery.isLoading ? "pending" : "error"}
              detail={autoEvaluateEnabled ? (stockfishAvailable ? "Detected" : "Unavailable") : "Auto-eval disabled"}
            />
          </div>
          {blockingErrors.length > 0 ? (
            <div className="mt-3 rounded-xl border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-3 py-2 text-sm text-[var(--color-error-text)]">
              <p className="font-semibold">Blocking issues</p>
              <ul className="mt-1 list-disc pl-4">
                {blockingErrors.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            <InfoChip label="Run ID" value={previewData?.run_id ?? "--"} />
            <InfoChip label="Config hash" value={previewData?.config_hash ?? validateMutation.data?.config_hash ?? "--"} />
            <InfoChip label="Scheduled games" value={previewData ? String(previewData.scheduled_games) : String(targetValidGames)} />
            <InfoChip label="Estimated cost (USD)" value={formatUsd(estimatedCostUsd, 4)} />
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-lg border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-2 text-sm font-semibold text-[var(--color-surface-canvas)]"
              disabled={!canLaunch}
              onClick={() => {
                if (!canLaunch) {
                  return;
                }
                if (!confirmLaunch("run", previewData?.run_id, previewData?.scheduled_games, estimatedCostUsd, autoEvaluateEnabled)) {
                  return;
                }
                startRunMutation.mutate(requestPayload, {
                  onSuccess: (job) => {
                    navigate({ to: "/dashboard/jobs/$jobId", params: { jobId: job.job_id } });
                  },
                });
              }}
            >
              {startRunMutation.isPending ? "Starting..." : "Launch Experiment"}
            </button>

            <button
              type="button"
              className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm font-semibold text-[var(--color-text-primary)]"
              disabled={!canLaunch}
              onClick={() => {
                if (!canLaunch) {
                  return;
                }
                if (!confirmLaunch("play", previewData?.run_id, 1, estimatedCostUsd, autoEvaluateEnabled)) {
                  return;
                }
                startPlayMutation.mutate(requestPayload, {
                  onSuccess: (job) => {
                    navigate({ to: "/dashboard/jobs/$jobId", params: { jobId: job.job_id } });
                  },
                });
              }}
            >
              {startPlayMutation.isPending ? "Starting..." : "Play (1 game)"}
            </button>

            <Link
              to="/dashboard/jobs"
              className="rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
            >
              Open Jobs
            </Link>
          </div>

          {(startRunMutation.isError || startPlayMutation.isError || modelCatalogQuery.isError || configsQuery.isError) && (
            <p className="mt-3 rounded-lg border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-3 py-2 text-sm text-[var(--color-error-text)]">
              {extractErrorMessage(startRunMutation.error) ||
                extractErrorMessage(startPlayMutation.error) ||
                extractErrorMessage(modelCatalogQuery.error) ||
                extractErrorMessage(configsQuery.error)}
            </p>
          )}

          <div className="mt-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Resolved config preview</p>
            <pre className="mt-2 max-h-[400px] max-w-full overflow-auto whitespace-pre-wrap break-words rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] p-3 font-['IBM_Plex_Mono'] text-xs text-[var(--color-text-primary)]">
              {toPrettyJson(resolvedConfigPreview)}
            </pre>
          </div>
        </section>
      </div>
    </section>
  );
}

function TemplateGroup({
  label,
  templates,
  selectedPath,
  onSelect,
}: {
  label: string;
  templates: TemplateOption[];
  selectedPath: string;
  onSelect: (path: string) => void;
}) {
  if (templates.length === 0) {
    return null;
  }
  return (
    <section className="mb-3">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">{label}</p>
      <div className="space-y-1">
        {templates.map((template) => (
          <button
            key={template.path}
            type="button"
            onClick={() => onSelect(template.path)}
            className={[
              "w-full rounded-lg border px-2.5 py-2 text-left",
              template.path === selectedPath
                ? "border-[var(--color-primary-700)] bg-[var(--color-primary-50)]"
                : "border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)]",
            ].join(" ")}
          >
            <p className="truncate text-sm font-semibold text-[var(--color-text-primary)]">{template.name}</p>
            <p className="truncate text-[11px] text-[var(--color-text-secondary)]">{template.path}</p>
          </button>
        ))}
      </div>
    </section>
  );
}

function ChecklistRow({ label, tone, detail }: { label: string; tone: "success" | "warning" | "error" | "pending"; detail: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <div>
        <p className="text-xs font-semibold text-[var(--color-text-primary)]">{label}</p>
        <p className="text-[11px] text-[var(--color-text-secondary)]">{detail}</p>
      </div>
      <StatusBadge label={toneLabel(tone)} tone={toneToBadgeTone(tone)} />
    </div>
  );
}

function InfoChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-1 truncate text-xs font-semibold text-[var(--color-text-primary)]">{value}</p>
    </div>
  );
}
function toneLabel(tone: "success" | "warning" | "error" | "pending"): string {
  if (tone === "success") {
    return "ok";
  }
  if (tone === "warning") {
    return "warning";
  }
  if (tone === "error") {
    return "blocked";
  }
  return "pending";
}

function toneToBadgeTone(tone: "success" | "warning" | "error" | "pending"): "success" | "warning" | "error" | "neutral" {
  if (tone === "success") {
    return "success";
  }
  if (tone === "warning") {
    return "warning";
  }
  if (tone === "error") {
    return "error";
  }
  return "neutral";
}

function buildStructuredOverrides(input: {
  provider: string;
  model: string;
  opponentMode: OpponentMode;
  opponentProvider: string;
  opponentModel: string;
  opponentStockfishLevel: number;
  targetValidGames: number;
  maxBudgetUsd: number | null;
  boardFormat: BoardFormat;
  provideLegalMoves: boolean;
  provideHistory: boolean;
  feedbackLevel: FeedbackLevel;
  autoEvaluateEnabled: boolean;
  evaluationPlayerColor: "white" | "black";
  evaluationOpponentElo: number | null;
}): string[] {
  const overrides: string[] = [
    `players.black.type=llm`,
    `players.black.provider=${input.provider}`,
    `players.black.model=${input.model}`,
    `players.black.name=${safeModelName(input.provider, input.model)}`,
    `experiment.target_valid_games=${input.targetValidGames}`,
    `strategy.board_format=${input.boardFormat}`,
    `strategy.provide_legal_moves=${input.provideLegalMoves}`,
    `strategy.provide_history=${input.provideHistory}`,
    `strategy.validation.feedback_level=${input.feedbackLevel}`,
  ];

  if (input.opponentMode === "random") {
    overrides.push("players.white.type=random");
    overrides.push("players.white.name=random_white");
  } else if (input.opponentMode === "stockfish") {
    overrides.push("players.white.type=engine");
    overrides.push("players.white.name=stockfish_white");
    overrides.push(`players.white.depth=${input.opponentStockfishLevel}`);
  } else if (input.opponentMode === "llm") {
    overrides.push("players.white.type=llm");
    overrides.push(`players.white.provider=${input.opponentProvider}`);
    overrides.push(`players.white.model=${input.opponentModel}`);
    overrides.push(`players.white.name=${safeModelName(input.opponentProvider, input.opponentModel)}`);
  }

  if (input.maxBudgetUsd !== null) {
    overrides.push(`experiment.max_budget_usd=${input.maxBudgetUsd}`);
  }

  if (input.autoEvaluateEnabled) {
    overrides.push("evaluation.auto.enabled=true");
    overrides.push(`evaluation.auto.player_color=${input.evaluationPlayerColor}`);
    if (input.evaluationOpponentElo !== null) {
      overrides.push(`evaluation.auto.opponent_elo=${input.evaluationOpponentElo}`);
    } else if (input.opponentMode === "stockfish") {
      overrides.push(`evaluation.auto.opponent_elo=${mapStockfishLevelToElo(input.opponentStockfishLevel)}`);
    }
  } else {
    overrides.push("evaluation.auto.enabled=false");
  }

  return overrides;
}

function parseOverrides(raw: string): string[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));
}

function upsertOverrides(existingRaw: string, updates: Record<string, string>): string {
  const existingLines = parseOverrides(existingRaw);
  const orderedKeys: string[] = [];
  const map = new Map<string, string>();

  for (const line of existingLines) {
    const parsed = parseOverrideLine(line);
    if (!parsed) {
      continue;
    }
    if (!orderedKeys.includes(parsed.key)) {
      orderedKeys.push(parsed.key);
    }
    map.set(parsed.key, parsed.value);
  }

  for (const [key, value] of Object.entries(updates)) {
    if (!orderedKeys.includes(key)) {
      orderedKeys.push(key);
    }
    map.set(key, value);
  }

  return orderedKeys.map((key) => `${key}=${map.get(key) ?? ""}`).join("\n");
}

function mergeOverrides(base: string[], custom: string[]): string[] {
  const order: string[] = [];
  const map = new Map<string, string>();

  const applyLine = (line: string) => {
    const parsed = parseOverrideLine(line);
    if (!parsed) {
      return;
    }
    if (!order.includes(parsed.key)) {
      order.push(parsed.key);
    }
    map.set(parsed.key, parsed.value);
  };

  for (const line of base) {
    applyLine(line);
  }
  for (const line of custom) {
    applyLine(line);
  }

  return order.map((key) => `${key}=${map.get(key) ?? ""}`);
}

function parseOverrideLine(line: string): { key: string; value: string } | null {
  const idx = line.indexOf("=");
  if (idx <= 0) {
    return null;
  }
  const key = line.slice(0, idx).trim();
  const value = line.slice(idx + 1).trim();
  if (!key) {
    return null;
  }
  return { key, value };
}

function resolveTemplateBucket(category: string | null | undefined, path: string): TemplateBucket {
  const normalizedCategory = (category ?? "").toLowerCase();
  const normalizedPath = path.toLowerCase();
  if (normalizedCategory.includes("custom") || normalizedPath.includes("/custom/")) {
    return "custom";
  }
  if (normalizedCategory.includes("ablation") || normalizedPath.includes("/ablations/")) {
    return "ablations";
  }
  return "baselines";
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

function parseOptionalPositiveNumber(value: string): number | null {
  if (value.trim().length === 0) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}
function parseOptionalInteger(value: string): number | null {
  if (value.trim().length === 0) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return parsed;
}

function clampInt(raw: string, minimum: number, maximum: number, fallback: number): number {
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(minimum, Math.min(maximum, parsed));
}

function confirmLaunch(
  mode: "run" | "play",
  runId: string | undefined,
  scheduledGames: number | undefined,
  estimatedCostUsd: number | null,
  autoEvaluateEnabled: boolean,
): boolean {
  const lines = [
    `Run ID: ${runId ?? "--"}`,
    `Scheduled games: ${scheduledGames ?? "--"}`,
    `Estimated cost: ${formatUsd(estimatedCostUsd, 4)}`,
    `Auto-evaluate: ${autoEvaluateEnabled ? "ON" : "OFF"}`,
    "",
    mode === "run" ? "Launch this experiment now?" : "Launch one quick play game now?",
  ];
  return window.confirm(lines.join("\n"));
}

function extractErrorMessage(error: unknown): string {
  if (!error) {
    return "";
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const value of values) {
    if (seen.has(value)) {
      continue;
    }
    seen.add(value);
    unique.push(value);
  }
  return unique;
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

