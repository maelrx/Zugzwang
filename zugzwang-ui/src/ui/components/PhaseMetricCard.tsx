import type { PhaseMetrics } from "../lib/runMetrics";

type ValueFormat = "decimal" | "percent";

type PhaseMetricCardProps = {
  title: string;
  description: string;
  values: PhaseMetrics;
  format: ValueFormat;
};

const PHASE_LABELS: Array<{ key: keyof PhaseMetrics; label: string }> = [
  { key: "opening", label: "Opening" },
  { key: "middlegame", label: "Middlegame" },
  { key: "endgame", label: "Endgame" },
];

export function PhaseMetricCard({ title, description, values, format }: PhaseMetricCardProps) {
  const maxValue = Math.max(...PHASE_LABELS.map((phase) => sanitizeMetricValue(values[phase.key])), 0);

  return (
    <article className="rounded-2xl border border-[#ddd5c8] bg-white/85 p-4">
      <header className="mb-3">
        <h4 className="text-sm font-semibold text-[#264351]">{title}</h4>
        <p className="mt-1 text-xs text-[#576d7a]">{description}</p>
      </header>

      <div className="space-y-2">
        {PHASE_LABELS.map((phase) => {
          const rawValue = values[phase.key];
          const value = sanitizeMetricValue(rawValue);
          const width = widthPercent(value, maxValue);
          return (
            <div key={phase.key} className="rounded-md border border-[#eee8dd] bg-[#faf7f1] px-2.5 py-2">
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-[#2b4351]">{phase.label}</p>
                <p className="text-xs text-[#2f4957]">{formatMetricValue(rawValue, format)}</p>
              </div>
              <div className="h-2 rounded-full bg-[#e8e3d9]">
                <div className="h-2 rounded-full bg-[#1f637d]" style={{ width: `${Math.max(0, Math.min(100, width))}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function sanitizeMetricValue(value: number | null): number {
  if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
    return value;
  }
  return 0;
}

function widthPercent(value: number, maxValue: number): number {
  if (maxValue <= 0) {
    return 0;
  }
  return (value / maxValue) * 100;
}

function formatMetricValue(value: number | null, format: ValueFormat): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  if (format === "percent") {
    return `${(value * 100).toFixed(1)}%`;
  }
  return value.toFixed(1);
}
