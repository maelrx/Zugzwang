import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { useEnvCheck, useModelCatalog } from "../../api/queries";
import { usePreferencesStore } from "../../stores/preferencesStore";
import { PageHeader } from "../components/PageHeader";

type ProviderTestSnapshot = {
  ok: boolean;
  checkedAt: number;
  message: string;
};

export function SettingsPage() {
  const envQuery = useEnvCheck();
  const catalogQuery = useModelCatalog();

  const defaultProvider = usePreferencesStore((state) => state.defaultProvider);
  const defaultModel = usePreferencesStore((state) => state.defaultModel);
  const autoEvaluate = usePreferencesStore((state) => state.autoEvaluate);
  const stockfishDepth = usePreferencesStore((state) => state.stockfishDepth);
  const notificationsEnabled = usePreferencesStore((state) => state.notificationsEnabled);
  const theme = usePreferencesStore((state) => state.theme);
  const setDefaultProvider = usePreferencesStore((state) => state.setDefaultProvider);
  const setDefaultModel = usePreferencesStore((state) => state.setDefaultModel);
  const setAutoEvaluate = usePreferencesStore((state) => state.setAutoEvaluate);
  const setStockfishDepth = usePreferencesStore((state) => state.setStockfishDepth);
  const setNotificationsEnabled = usePreferencesStore((state) => state.setNotificationsEnabled);
  const setTheme = usePreferencesStore((state) => state.setTheme);

  const checks = envQuery.data ?? [];
  const checksByProvider = useMemo(() => {
    const map = new Map<string, { ok: boolean; message: string }>();
    for (const item of checks) {
      map.set(item.provider, { ok: item.ok, message: item.message });
    }
    return map;
  }, [checks]);

  const providerCatalog = useMemo(() => catalogQuery.data ?? [], [catalogQuery.data]);
  const providerNames = useMemo(() => {
    const names = new Set<string>();
    for (const preset of providerCatalog) {
      names.add(preset.provider);
    }
    for (const item of checks) {
      if (item.provider !== "stockfish") {
        names.add(item.provider);
      }
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [checks, providerCatalog]);

  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [providerTests, setProviderTests] = useState<Record<string, ProviderTestSnapshot>>({});

  useEffect(() => {
    if (defaultProvider || providerCatalog.length === 0) {
      return;
    }
    setDefaultProvider(providerCatalog[0].provider);
  }, [defaultProvider, providerCatalog, setDefaultProvider]);

  const selectedPreset = useMemo(
    () => providerCatalog.find((preset) => preset.provider === defaultProvider) ?? providerCatalog[0] ?? null,
    [defaultProvider, providerCatalog],
  );

  const availableModels = selectedPreset?.models ?? [];
  useEffect(() => {
    if (!selectedPreset) {
      if (defaultModel !== null) {
        setDefaultModel(null);
      }
      return;
    }
    const isSelectedValid = defaultModel ? availableModels.some((model) => model.id === defaultModel) : false;
    if (isSelectedValid) {
      return;
    }
    const fallback = availableModels.find((model) => model.recommended)?.id ?? availableModels[0]?.id ?? null;
    if (fallback !== defaultModel) {
      setDefaultModel(fallback);
    }
  }, [availableModels, defaultModel, selectedPreset, setDefaultModel]);

  const stockfishCheck = checksByProvider.get("stockfish");
  const readyCount = checks.filter((item) => item.ok).length;
  const allReady = checks.length > 0 && readyCount === checks.length;

  return (
    <section>
      <PageHeader
        eyebrow="Settings"
        title="Environment Diagnostics"
        subtitle="Provider readiness, Stockfish defaults, and persisted preferences."
      />

      <section className="mb-4 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Providers Health</h3>
          <button
            type="button"
            onClick={() => void runProviderTest("all", envQuery, setProviderTests, setTestingProvider)}
            disabled={envQuery.isFetching}
            className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-primary)] disabled:opacity-60"
          >
            {envQuery.isFetching ? "Refreshing..." : "Refresh all"}
          </button>
        </div>

        {!envQuery.isLoading && !envQuery.isError ? (
          <div
            className={[
              "mt-2 rounded-lg border px-3 py-2 text-sm",
              allReady ? "border-[var(--color-success-border)] bg-[var(--color-success-bg)] text-[var(--color-success-text)]" : "border-[var(--color-warning-border)] bg-[var(--color-warning-bg)] text-[var(--color-warning-text)]",
            ].join(" ")}
          >
            Readiness: {readyCount}/{checks.length} checks passing.
          </div>
        ) : null}

        {envQuery.isLoading ? <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Loading provider checks...</p> : null}
        {envQuery.isError ? (
          <p className="mt-2 rounded-lg border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-3 py-2 text-sm text-[var(--color-error-text)]">
            Failed to load provider diagnostics.
          </p>
        ) : null}

        <div className="mt-3 space-y-2">
          {providerNames.map((provider) => {
            const preset = providerCatalog.find((item) => item.provider === provider);
            const check = checksByProvider.get(provider);
            const tested = providerTests[provider];
            const configured = check?.ok === true;
            const models = preset?.models ?? [];
            return (
              <article key={provider} className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-[var(--color-text-primary)]">{preset?.provider_label ?? provider}</p>
                    <span className={configured ? statusClass("configured") : statusClass("missing")}>{configured ? "configured" : "missing"}</span>
                    {tested ? (
                      <span className={tested.ok ? statusClass("reachable") : statusClass("unreachable")}>
                        {tested.ok ? "reachable" : "unreachable"}
                      </span>
                    ) : (
                      <span className={statusClass("neutral")}>not tested</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => void runProviderTest(provider, envQuery, setProviderTests, setTestingProvider)}
                    disabled={testingProvider !== null}
                    className="rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface-raised)] px-2.5 py-1 text-xs font-semibold text-[var(--color-text-primary)] disabled:opacity-60"
                  >
                    {testingProvider === provider ? "Testing..." : "Test"}
                  </button>
                </div>
                <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{check?.message ?? "No env-check response for this provider."}</p>
                <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Env var: {preset?.api_key_env ?? "unknown"}</p>
                <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                  Models: {models.length > 0 ? models.map((model) => model.id).join(", ") : "none from catalog"}
                </p>
                {tested ? (
                  <p className="mt-1 text-[11px] text-[var(--color-text-muted)]">
                    Last test: {formatTimestamp(tested.checkedAt)} | {tested.message}
                  </p>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>

      <section className="mb-4 rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Stockfish</h3>
          <button
            type="button"
            onClick={() => void runProviderTest("stockfish", envQuery, setProviderTests, setTestingProvider)}
            disabled={testingProvider !== null}
            className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-surface-canvas)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-primary)] disabled:opacity-60"
          >
            {testingProvider === "stockfish" ? "Testing..." : "Test"}
          </button>
        </div>

        <div className="mt-2 rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={stockfishCheck?.ok ? statusClass("configured") : statusClass("missing")}>
              {stockfishCheck?.ok ? "found" : "not found"}
            </span>
            <span className="text-xs text-[var(--color-text-secondary)]">{stockfishCheck?.message ?? "Waiting for env-check..."}</span>
          </div>
          {!stockfishCheck?.ok ? (
            <p className="mt-1 text-xs text-[var(--color-warning-text)]">
              Auto-evaluation defaults to OFF when Stockfish is unavailable.
            </p>
          ) : null}
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm text-[var(--color-text-primary)]">
            <span className="flex items-center justify-between gap-2">
              <span>Auto-evaluate by default</span>
              <input
                type="checkbox"
                checked={autoEvaluate}
                onChange={(event) => setAutoEvaluate(event.target.checked)}
                className="h-4 w-4 rounded border-[var(--color-border-strong)]"
              />
            </span>
          </label>

          <label className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm text-[var(--color-text-primary)]">
            Default evaluation depth
            <input
              type="number"
              min={1}
              max={30}
              step={1}
              value={stockfishDepth}
              onChange={(event) => setStockfishDepth(Number(event.target.value))}
              className="mt-1 w-full rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-2 py-1 text-sm"
            />
          </label>
        </div>
      </section>

      <section className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-card)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Preferences</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-[var(--color-text-secondary)]">
            Default provider
            <select
              value={selectedPreset?.provider ?? ""}
              onChange={(event) => setDefaultProvider(event.target.value || null)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            >
              {providerCatalog.map((preset) => (
                <option key={preset.provider} value={preset.provider}>
                  {preset.provider_label}
                </option>
              ))}
            </select>
          </label>

          <label className="text-xs text-[var(--color-text-secondary)]">
            Default model
            <select
              value={defaultModel ?? ""}
              onChange={(event) => setDefaultModel(event.target.value || null)}
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            >
              {availableModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.label}
                </option>
              ))}
            </select>
          </label>

          <label className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-canvas)] px-3 py-2 text-sm text-[var(--color-text-primary)]">
            <span className="flex items-center justify-between gap-2">
              <span>Notifications</span>
              <input
                type="checkbox"
                checked={notificationsEnabled}
                onChange={(event) => setNotificationsEnabled(event.target.checked)}
                className="h-4 w-4 rounded border-[var(--color-border-strong)]"
              />
            </span>
          </label>

          <label className="text-xs text-[var(--color-text-secondary)]">
            Theme
            <select
              value={theme}
              onChange={(event) => setTheme(event.target.value === "light" ? "light" : "light")}
              className="mt-1 w-full rounded-lg border border-[var(--color-border-default)] bg-[var(--color-surface-canvas)] px-2.5 py-2 text-sm text-[var(--color-text-primary)]"
            >
              <option value="light">Light</option>
            </select>
          </label>
        </div>
        <p className="mt-2 text-xs text-[var(--color-text-secondary)]">Preferences are persisted locally in `zugzwang-preferences-v2`.</p>
      </section>
    </section>
  );
}

async function runProviderTest(
  provider: string,
  envQuery: ReturnType<typeof useEnvCheck>,
  setProviderTests: Dispatch<SetStateAction<Record<string, ProviderTestSnapshot>>>,
  setTestingProvider: Dispatch<SetStateAction<string | null>>,
) {
  setTestingProvider(provider);
  try {
    const refreshed = await envQuery.refetch();
    const checks = refreshed.data ?? [];
    const now = Date.now();

    if (provider === "all") {
      const next: Record<string, ProviderTestSnapshot> = {};
      for (const item of checks) {
        next[item.provider] = { ok: item.ok, checkedAt: now, message: item.message };
      }
      setProviderTests((prev) => ({ ...prev, ...next }));
      return;
    }

    const matched = checks.find((item) => item.provider === provider);
    setProviderTests((prev) => ({
      ...prev,
      [provider]: {
        ok: matched?.ok ?? false,
        checkedAt: now,
        message: matched?.message ?? "No env-check response for this provider.",
      },
    }));
  } catch (error) {
    if (provider !== "all") {
      setProviderTests((prev) => ({
        ...prev,
        [provider]: {
          ok: false,
          checkedAt: Date.now(),
          message: `Test failed: ${formatProviderTestError(error)}`,
        },
      }));
    }
  } finally {
    setTestingProvider(null);
  }
}

function statusClass(kind: "configured" | "reachable" | "unreachable" | "missing" | "neutral"): string {
  if (kind === "configured" || kind === "reachable") {
    return "rounded-full border border-[var(--color-success-border)] bg-[var(--color-success-bg)] px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-success-text)]";
  }
  if (kind === "missing" || kind === "unreachable") {
    return "rounded-full border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-error-text)]";
  }
  return "rounded-full border border-[var(--color-border-default)] bg-[var(--color-surface-sunken)] px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-secondary)]";
}

function formatTimestamp(timestamp: number): string {
  try {
    return new Date(timestamp).toLocaleString();
  } catch {
    return "--";
  }
}

function formatProviderTestError(error: unknown): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return "Unknown error";
}
