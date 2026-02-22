import { useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../../api/client";
import { useConfigs, useModelCatalog, usePreviewConfig, useStartPlay, useStartRun, useValidateConfig } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function RunLabPage() {
  const configsQuery = useConfigs();
  const validateMutation = useValidateConfig();
  const previewMutation = usePreviewConfig();
  const startRunMutation = useStartRun();
  const startPlayMutation = useStartPlay();
  const modelCatalogQuery = useModelCatalog();
  const navigate = useNavigate();

  const [selectedConfigPath, setSelectedConfigPath] = useState("");
  const [modelProfile, setModelProfile] = useState("");
  const [overridesText, setOverridesText] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModel, setSelectedModel] = useState("");

  const templates = useMemo(() => {
    const baselines = (configsQuery.data?.baselines ?? []).map((item) => ({ ...item, bucket: "Baselines" }));
    const ablations = (configsQuery.data?.ablations ?? []).map((item) => ({ ...item, bucket: "Ablations" }));
    return [...baselines, ...ablations];
  }, [configsQuery.data?.ablations, configsQuery.data?.baselines]);

  const currentConfigPath = selectedConfigPath || templates[0]?.path || "";
  const parsedOverrides = useMemo(() => parseOverrides(overridesText), [overridesText]);
  const invalidOverrideLines = useMemo(() => parsedOverrides.filter((line) => !line.includes("=")), [parsedOverrides]);
  const providerPresets = modelCatalogQuery.data ?? [];
  const effectiveProvider = selectedProvider || providerPresets[0]?.provider || "";
  const activePreset = useMemo(
    () => providerPresets.find((preset) => preset.provider === effectiveProvider) ?? null,
    [effectiveProvider, providerPresets],
  );
  const recommendedModel = activePreset?.models.find((model) => model.recommended)?.id || activePreset?.models[0]?.id || "";
  const effectiveModel = selectedModel || recommendedModel;

  const baselineCount = configsQuery.data?.baselines?.length ?? 0;
  const ablationCount = configsQuery.data?.ablations?.length ?? 0;
  const isLaunching = startRunMutation.isPending || startPlayMutation.isPending;

  useEffect(() => {
    if (!selectedProvider && providerPresets[0]?.provider) {
      setSelectedProvider(providerPresets[0].provider);
    }
  }, [providerPresets, selectedProvider]);

  useEffect(() => {
    if (!activePreset) {
      setSelectedModel("");
      return;
    }
    if (!activePreset.models.some((item) => item.id === selectedModel)) {
      const next = activePreset.models.find((item) => item.recommended)?.id || activePreset.models[0]?.id || "";
      setSelectedModel(next);
    }
  }, [activePreset, selectedModel]);

  return (
    <section>
      <PageHeader
        eyebrow="Run Lab"
        title="Experiment Launch Workbench"
        subtitle="Configure, validate, preview and launch jobs directly from the UI."
      />

      <div className="rounded-2xl border border-[#d5cfc4] bg-white/80 p-5 shadow-[0_10px_24px_rgba(12,30,42,0.07)]">
        <p className="mb-3 text-xs uppercase tracking-[0.15em] text-[#607786]">
          Templates loaded: {configsQuery.isLoading ? "..." : `${baselineCount} baselines / ${ablationCount} ablations`}
        </p>

        {configsQuery.isError && (
          <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff0ed] px-3 py-2 text-sm text-[#8a3434]">
            Failed to load `/api/configs`.
          </p>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-xl border border-[#ded8cf] bg-[#f9f6ef] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[#26404f]">Inputs</h3>

            <div className="mb-3 rounded-lg border border-[#d7d0c2] bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[#5f7481]">Quick Model Selector</p>

              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <label className="text-xs text-[#516977]">
                  Provider
                  <select
                    value={effectiveProvider}
                    onChange={(event) => setSelectedProvider(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-[#d7d0c2] bg-white px-2.5 py-2 text-sm text-[#2f4957]"
                  >
                    {providerPresets.map((preset) => (
                      <option key={preset.provider} value={preset.provider}>
                        {preset.provider_label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="text-xs text-[#516977]">
                  Model
                  <select
                    value={effectiveModel}
                    onChange={(event) => setSelectedModel(event.target.value)}
                    className="mt-1 w-full rounded-lg border border-[#d7d0c2] bg-white px-2.5 py-2 text-sm text-[#2f4957]"
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

              <button
                type="button"
                className="mt-2 rounded-md border border-[#1f637d] bg-[#1f637d] px-3 py-1.5 text-xs font-semibold text-[#edf8fd]"
                disabled={!activePreset || !effectiveModel}
                onClick={() => {
                  if (!activePreset || !effectiveModel) {
                    return;
                  }
                  const safeName = `${activePreset.provider}_${effectiveModel}`.replace(/[^a-zA-Z0-9_-]+/g, "_");
                  setOverridesText((prev) =>
                    upsertOverrides(prev, {
                      "players.black.type": "llm",
                      "players.black.provider": activePreset.provider,
                      "players.black.model": effectiveModel,
                      "players.black.name": safeName,
                    }),
                  );
                }}
              >
                Apply Preset to Overrides
              </button>

              {activePreset && (
                <p className="mt-2 text-[11px] text-[#57707e]">
                  API: {activePreset.api_style} | Base URL: {activePreset.base_url} | Secret: {activePreset.api_key_env}
                </p>
              )}

              {activePreset?.notes && <p className="mt-1 text-[11px] text-[#57707e]">{activePreset.notes}</p>}

              {modelCatalogQuery.isError && (
                <p className="mt-2 rounded-md border border-[#cf8f8f] bg-[#fff2ef] px-2.5 py-1.5 text-xs text-[#8a3434]">
                  Failed to load `/api/configs/model-catalog`.
                </p>
              )}
            </div>

            <label className="mb-3 block text-xs text-[#516977]">
              Config template
              <select
                value={currentConfigPath}
                onChange={(event) => setSelectedConfigPath(event.target.value)}
                className="mt-1 w-full rounded-lg border border-[#d7d0c2] bg-white px-2.5 py-2 text-sm text-[#2f4957]"
              >
                {templates.map((item) => (
                  <option key={item.path} value={item.path}>
                    [{item.bucket}] {item.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="mb-3 block text-xs text-[#516977]">
              Model profile (optional)
              <input
                value={modelProfile}
                onChange={(event) => setModelProfile(event.target.value)}
                placeholder="configs/models/..."
                className="mt-1 w-full rounded-lg border border-[#d7d0c2] bg-white px-2.5 py-2 text-sm text-[#2f4957]"
              />
            </label>

            <label className="mb-3 block text-xs text-[#516977]">
              Overrides (`key=value`, one per line)
              <textarea
                value={overridesText}
                onChange={(event) => setOverridesText(event.target.value)}
                rows={8}
                placeholder="experiment.target_valid_games=5"
                className="mt-1 w-full rounded-lg border border-[#d7d0c2] bg-white px-2.5 py-2 font-['IBM_Plex_Mono'] text-xs text-[#2f4957]"
              />
            </label>

            {invalidOverrideLines.length > 0 && (
              <p className="rounded-md border border-[#cf8f8f] bg-[#fff2ef] px-2.5 py-1.5 text-xs text-[#8a3434]">
                Invalid override line(s): {invalidOverrideLines.join(", ")}
              </p>
            )}
          </section>

          <section className="rounded-xl border border-[#ded8cf] bg-[#f9f6ef] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[#26404f]">Actions</h3>

            <div className="mb-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded-md border border-[#2b6985] bg-[#2b6985] px-3 py-1.5 text-xs font-semibold text-[#eef8fd]"
                disabled={!currentConfigPath || invalidOverrideLines.length > 0 || validateMutation.isPending}
                onClick={() =>
                  validateMutation.mutate({
                    config_path: currentConfigPath,
                    model_profile: modelProfile.trim() || null,
                    overrides: parsedOverrides,
                  })
                }
              >
                {validateMutation.isPending ? "Validating..." : "Validate"}
              </button>

              <button
                type="button"
                className="rounded-md border border-[#2b6985] bg-[#2b6985] px-3 py-1.5 text-xs font-semibold text-[#eef8fd]"
                disabled={!currentConfigPath || invalidOverrideLines.length > 0 || previewMutation.isPending}
                onClick={() =>
                  previewMutation.mutate({
                    config_path: currentConfigPath,
                    model_profile: modelProfile.trim() || null,
                    overrides: parsedOverrides,
                  })
                }
              >
                {previewMutation.isPending ? "Previewing..." : "Preview"}
              </button>
            </div>

            <div className="mb-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded-md border border-[#1f637d] bg-[#1f637d] px-3 py-1.5 text-xs font-semibold text-[#edf8fd]"
                disabled={!currentConfigPath || invalidOverrideLines.length > 0 || isLaunching}
                onClick={() =>
                  startPlayMutation.mutate(
                    {
                      config_path: currentConfigPath,
                      model_profile: modelProfile.trim() || null,
                      overrides: parsedOverrides,
                    },
                    {
                      onSuccess: (job) =>
                        navigate({
                          to: "/jobs/$jobId",
                          params: { jobId: job.job_id },
                        }),
                    },
                  )
                }
              >
                {startPlayMutation.isPending ? "Starting..." : "Play (1 game)"}
              </button>

              <button
                type="button"
                className="rounded-md border border-[#1f637d] bg-[#1f637d] px-3 py-1.5 text-xs font-semibold text-[#edf8fd]"
                disabled={!currentConfigPath || invalidOverrideLines.length > 0 || isLaunching}
                onClick={() =>
                  startRunMutation.mutate(
                    {
                      config_path: currentConfigPath,
                      model_profile: modelProfile.trim() || null,
                      overrides: parsedOverrides,
                    },
                    {
                      onSuccess: (job) =>
                        navigate({
                          to: "/jobs/$jobId",
                          params: { jobId: job.job_id },
                        }),
                    },
                  )
                }
              >
                {startRunMutation.isPending ? "Starting..." : "Run"}
              </button>
            </div>

            <StatusBox
              label="Validation"
              text={
                validateMutation.data
                  ? `${validateMutation.data.ok ? "ok" : "failed"}: ${validateMutation.data.message}`
                  : "Run validation to check config integrity."
              }
              tone={validateMutation.data?.ok ? "good" : validateMutation.isError ? "bad" : "neutral"}
            />

            <StatusBox
              label="Preview"
              text={
                previewMutation.data
                  ? `run_id=${previewMutation.data.run_id} | scheduled=${previewMutation.data.scheduled_games} | est_cost=${formatCost(previewMutation.data.estimated_total_cost_usd)}`
                  : "Run preview to get run id, hash and cost estimation."
              }
              tone={previewMutation.isError ? "bad" : previewMutation.data ? "good" : "neutral"}
            />

            {(validateMutation.isError || previewMutation.isError || startRunMutation.isError || startPlayMutation.isError) && (
              <p className="mt-3 rounded-md border border-[#cf8f8f] bg-[#fff2ef] px-2.5 py-1.5 text-xs text-[#8a3434]">
                {extractErrorMessage(validateMutation.error) ||
                  extractErrorMessage(previewMutation.error) ||
                  extractErrorMessage(startPlayMutation.error) ||
                  extractErrorMessage(startRunMutation.error)}
              </p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
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
    if (!line.includes("=")) {
      continue;
    }
    const idx = line.indexOf("=");
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (!key) {
      continue;
    }
    if (!orderedKeys.includes(key)) {
      orderedKeys.push(key);
    }
    map.set(key, value);
  }

  for (const [key, value] of Object.entries(updates)) {
    if (!orderedKeys.includes(key)) {
      orderedKeys.push(key);
    }
    map.set(key, value);
  }

  return orderedKeys.map((key) => `${key}=${map.get(key) ?? ""}`).join("\n");
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

function formatCost(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return value.toFixed(4);
}

function StatusBox({ label, text, tone }: { label: string; text: string; tone: "good" | "bad" | "neutral" }) {
  return (
    <div
      className={[
        "mt-2 rounded-md border px-2.5 py-1.5 text-xs",
        tone === "good"
          ? "border-[#99c7ac] bg-[#eaf8f0] text-[#24583f]"
          : tone === "bad"
            ? "border-[#cf8f8f] bg-[#fff2ef] text-[#8a3434]"
            : "border-[#cfd7dc] bg-[#f3f7fa] text-[#48616f]",
      ].join(" ")}
    >
      <span className="font-semibold">{label}:</span> {text}
    </div>
  );
}
