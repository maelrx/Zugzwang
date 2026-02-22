import type { PhaseMetrics } from "../lib/runMetrics";

type ValueFormat = "decimal" | "percent";

type PhaseMetricCompareCardProps = {
  title: string;
  description: string;
  leftLabel: string;
  rightLabel: string;
  leftValues: PhaseMetrics;
  rightValues: PhaseMetrics;
  format: ValueFormat;
  lowerIsBetter?: boolean;
};

const PHASE_LABELS: Array<{ key: keyof PhaseMetrics; label: string }> = [
  { key: "opening", label: "Opening" },
  { key: "middlegame", label: "Middlegame" },
  { key: "endgame", label: "Endgame" },
];

export function PhaseMetricCompareCard({
  title,
  description,
  leftLabel,
  rightLabel,
  leftValues,
  rightValues,
  format,
  lowerIsBetter = false,
}: PhaseMetricCompareCardProps) {
  const maxValue = Math.max(
    ...PHASE_LABELS.flatMap((phase) => [sanitizeMetricValue(leftValues[phase.key]), sanitizeMetricValue(rightValues[phase.key])]),
    0,
  );

  return (
    <article className="rounded-2xl border border-[#ddd5c8] bg-white/85 p-4">
      <header className="mb-3">
        <h4 className="text-sm font-semibold text-[#264351]">{title}</h4>
        <p className="mt-1 text-xs text-[#576d7a]">{description}</p>
      </header>

      <div className="mb-2 grid grid-cols-[1fr_auto_auto] gap-3 px-1 text-[11px] uppercase tracking-[0.12em] text-[#627786]">
        <span>Phase</span>
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>

      <div className="space-y-2">
        {PHASE_LABELS.map((phase) => {
          const left = leftValues[phase.key];
          const right = rightValues[phase.key];
          const leftValue = sanitizeMetricValue(left);
          const rightValue = sanitizeMetricValue(right);
          const leftWidth = widthPercent(leftValue, maxValue);
          const rightWidth = widthPercent(rightValue, maxValue);
          const winner = pickWinner(leftValue, rightValue, lowerIsBetter);

          return (
            <div key={phase.key} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-md border border-[#eee8dd] bg-[#faf7f1] px-2.5 py-2">
              <div>
                <p className="text-xs font-semibold text-[#2b4351]">{phase.label}</p>
                <div className="mt-1 space-y-1">
                  <MetricBar width={leftWidth} tone="left" />
                  <MetricBar width={rightWidth} tone="right" />
                </div>
              </div>
              <div className="min-w-20 text-right text-xs text-[#2f4957]">{formatMetricValue(left, format)}</div>
              <div className="min-w-20 text-right text-xs text-[#2f4957]">
                {formatMetricValue(right, format)}
                {winner && <span className={winner === "left" ? "ml-1 text-[#1f6a49]" : "ml-1 text-[#8d3131]"}>{winner === "left" ? "A" : "B"}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function MetricBar({ width, tone }: { width: number; tone: "left" | "right" }) {
  return (
    <div className="h-2 rounded-full bg-[#e8e3d9]">
      <div
        className={tone === "left" ? "h-2 rounded-full bg-[#1f637d]" : "h-2 rounded-full bg-[#b46e35]"}
        style={{ width: `${Math.max(0, Math.min(100, width))}%` }}
      />
    </div>
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

function pickWinner(left: number, right: number, lowerIsBetter: boolean): "left" | "right" | null {
  if (left === 0 && right === 0) {
    return null;
  }
  if (Math.abs(left - right) < 1e-6) {
    return null;
  }
  if (lowerIsBetter) {
    return left < right ? "left" : "right";
  }
  return left > right ? "left" : "right";
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
