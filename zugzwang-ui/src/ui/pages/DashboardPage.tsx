import { InfoCard } from "../components/InfoCard";
import { PageHeader } from "../components/PageHeader";

export function DashboardPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Home"
        title="Research Operations Dashboard"
        subtitle="This is the frontend migration shell. Data widgets will switch to live API hooks in M4 and M5."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <InfoCard title="Active jobs" value="0" hint="Polled from /api/jobs in the next milestone." />
        <InfoCard title="Runs indexed" value="--" hint="Will read /api/runs once query hooks are wired." />
        <InfoCard title="Total spend" value="--" hint="Derived from experiment reports." />
        <InfoCard title="Completion rate" value="--" hint="Aggregated from run summaries." />
      </div>
    </section>
  );
}

