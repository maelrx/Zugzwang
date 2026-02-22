import { useEnvCheck } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function SettingsPage() {
  const envQuery = useEnvCheck();
  const checks = envQuery.data ?? [];

  return (
    <section>
      <PageHeader
        eyebrow="Settings"
        title="Environment Diagnostics"
        subtitle="Provider and stockfish readiness checks from /api/env-check will be displayed here."
      />

      <div className="space-y-3 rounded-2xl border border-[#d9d4c8] bg-white/80 p-5">
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
              className="flex items-center justify-between rounded-lg border border-[#e7e0d4] bg-[#fbfaf7] px-3 py-2"
            >
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
          ))}
      </div>
    </section>
  );
}
