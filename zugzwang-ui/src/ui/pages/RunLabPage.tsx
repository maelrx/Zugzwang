import { useConfigs } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

const RUN_LAB_CHECKLIST = [
  "Config picker wired to /api/configs",
  "Override editor with dotted-path parsing",
  "Validate and preview via mutation hooks",
  "Start Run / Play actions redirecting to job detail",
];

export function RunLabPage() {
  const configsQuery = useConfigs();
  const baselineCount = configsQuery.data?.baselines?.length ?? 0;
  const ablationCount = configsQuery.data?.ablations?.length ?? 0;

  return (
    <section>
      <PageHeader
        eyebrow="Run Lab"
        title="Experiment Launch Workbench"
        subtitle="This page will become the main flow for config validation, preview and launch."
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

        <p className="mb-3 text-sm font-semibold text-[#26404f]">Implementation queue</p>
        <ul className="space-y-2 text-sm text-[#445966]">
          {RUN_LAB_CHECKLIST.map((item) => (
            <li key={item} className="rounded-lg border border-[#e5e0d7] bg-[#f9f7f2] px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
