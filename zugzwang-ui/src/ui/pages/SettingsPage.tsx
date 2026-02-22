import { PageHeader } from "../components/PageHeader";

export function SettingsPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Settings"
        title="Environment Diagnostics"
        subtitle="Provider and stockfish readiness checks from /api/env-check will be displayed here."
      />

      <div className="rounded-2xl border border-[#d9d4c8] bg-white/80 p-5">
        <p className="text-sm font-semibold text-[#284451]">Current mode</p>
        <p className="mt-2 text-sm text-[#4f6774]">
          Read-only settings view. Editing `.env` remains outside the UI by design.
        </p>
      </div>
    </section>
  );
}

