import { PageHeader } from "../components/PageHeader";

export function JobsPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Jobs"
        title="Execution Monitor"
        subtitle="Real-time job status and SSE logs will be rendered here from /api/jobs and /api/jobs/{id}/logs."
      />

      <div className="rounded-2xl border border-dashed border-[#9bb2be] bg-[#f7fbfd] p-5 text-sm text-[#355362]">
        <p className="font-semibold">Planned next</p>
        <p className="mt-2">
          Jobs table, status badges, progress bar, and a live terminal panel with stdout/stderr stream and done signal.
        </p>
      </div>
    </section>
  );
}

