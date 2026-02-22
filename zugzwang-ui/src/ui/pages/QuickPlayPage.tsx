import { Link } from "@tanstack/react-router";
import { PageHeader } from "../components/PageHeader";

export function QuickPlayPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Quick Play"
        title="Quick Play"
        subtitle="Foundation milestone placeholder. Full 1-click live game flow lands in M4."
      />

      <div className="rounded-2xl border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] p-5 shadow-[var(--shadow-card)]">
        <p className="text-sm text-[var(--color-text-secondary)]">
          This route is now part of V2 navigation. During M1, it remains a lightweight entry point while we keep existing launch flows available.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            to="/lab"
            className="rounded-md border border-[var(--color-primary-700)] bg-[var(--color-primary-700)] px-3 py-1.5 text-sm font-semibold text-[var(--color-surface-canvas)]"
          >
            Open Experiment Lab
          </Link>
          <Link
            to="/runs"
            className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-surface-raised)] px-3 py-1.5 text-sm text-[var(--color-text-primary)]"
          >
            Open Runs Explorer
          </Link>
        </div>
      </div>
    </section>
  );
}

