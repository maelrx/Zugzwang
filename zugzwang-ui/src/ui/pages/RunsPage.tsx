import { PageHeader } from "../components/PageHeader";

export function RunsPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Runs"
        title="Run Explorer"
        subtitle="Run list, summary tabs, and replay navigation will live here once API query hooks are connected."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-2xl border border-[#ddd7cd] bg-white/80 p-5">
          <p className="text-sm font-semibold text-[#254150]">/runs list</p>
          <p className="mt-2 text-sm text-[#4f6874]">Search, evaluated filter, sortable columns and quick navigation to details.</p>
        </article>
        <article className="rounded-2xl border border-[#ddd7cd] bg-white/80 p-5">
          <p className="text-sm font-semibold text-[#254150]">Run detail tabs</p>
          <p className="mt-2 text-sm text-[#4f6874]">Overview, move quality, game list, resolved config and evaluation launcher.</p>
        </article>
      </div>
    </section>
  );
}

