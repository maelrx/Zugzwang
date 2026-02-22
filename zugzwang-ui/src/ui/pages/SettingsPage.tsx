import { useEnvCheck } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function SettingsPage() {
  const envQuery = useEnvCheck();
  const checks = envQuery.data ?? [];
  const readyCount = checks.filter((item) => item.ok).length;
  const allReady = checks.length > 0 && readyCount === checks.length;
  const missingProviders = checks.filter((item) => !item.ok).map((item) => item.provider);

  return (
    <section>
      <PageHeader
        eyebrow="Settings"
        title="Environment Diagnostics"
        subtitle="Provider and Stockfish readiness checks loaded directly from `/api/env-check`."
      />

      <div className="space-y-3 rounded-2xl border border-[#d9d4c8] bg-white/80 p-5">
        {!envQuery.isLoading && !envQuery.isError && (
          <div
            className={[
              "rounded-xl border px-3 py-2 text-sm",
              allReady ? "border-[#99c7ac] bg-[#eaf8f0] text-[#24583f]" : "border-[#d7b071] bg-[#fff3de] text-[#7d5618]",
            ].join(" ")}
          >
            <p className="font-semibold">
              Readiness: {readyCount}/{checks.length} checks passing
            </p>
            {!allReady && missingProviders.length > 0 && (
              <p className="mt-1 text-xs">Missing: {missingProviders.join(", ")}</p>
            )}
          </div>
        )}

        {envQuery.isLoading && <p className="text-sm text-[#4f6774]">Loading provider checks...</p>}

        {envQuery.isError && (
          <p className="rounded-lg border border-[#cf8f8f] bg-[#fff2f0] px-3 py-2 text-sm text-[#8a3434]">
            Failed to load `/api/env-check`.
          </p>
        )}

        {!envQuery.isLoading &&
          !envQuery.isError &&
          checks.map((item) => (
            <div
              key={item.provider}
              className="rounded-lg border border-[#e7e0d4] bg-[#fbfaf7] px-3 py-2"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-[#2a4351]">{item.provider}</span>
                <span
                  className={[
                    "rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.08em]",
                    item.ok ? "bg-[#dcf7e7] text-[#1c6a41]" : "bg-[#ffe9e5] text-[#8b3930]",
                  ].join(" ")}
                >
                  {item.ok ? "ok" : "missing"}
                </span>
              </div>
              <p className="mt-1 text-xs text-[#516977]">{item.message}</p>
            </div>
          ))}
      </div>
    </section>
  );
}
