import type { MoveQualityCounts } from "../lib/moveQuality";
import { formatMoveQualityLabel, moveQualityPercentages } from "../lib/moveQuality";

type MoveQualityDistributionCompareCardProps = {
  title: string;
  description: string;
  leftLabel: string;
  rightLabel: string;
  leftCounts: MoveQualityCounts;
  rightCounts: MoveQualityCounts;
};

const ORDER: Array<Exclude<keyof MoveQualityCounts, "total">> = ["clean", "recovered", "illegal", "parseFail"];

export function MoveQualityDistributionCompareCard({
  title,
  description,
  leftLabel,
  rightLabel,
  leftCounts,
  rightCounts,
}: MoveQualityDistributionCompareCardProps) {
  const leftRates = moveQualityPercentages(leftCounts);
  const rightRates = moveQualityPercentages(rightCounts);

  return (
    <article className="rounded-2xl border border-[#ddd5c8] bg-white/85 p-4">
      <header className="mb-3">
        <h4 className="text-sm font-semibold text-[#264351]">{title}</h4>
        <p className="mt-1 text-xs text-[#576d7a]">{description}</p>
      </header>

      <div className="mb-2 grid grid-cols-[1fr_auto_auto] gap-3 px-1 text-[11px] uppercase tracking-[0.12em] text-[#627786]">
        <span>Class</span>
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>

      <div className="space-y-2">
        {ORDER.map((key) => {
          const leftPercent = leftRates[key];
          const rightPercent = rightRates[key];
          const winner = compareHigherIsBetter(leftPercent, rightPercent);
          return (
            <div key={key} className="rounded-md border border-[#eee8dd] bg-[#faf7f1] px-2.5 py-2">
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-[#2b4351]">{formatMoveQualityLabel(key)}</p>
                <p className="text-xs text-[#2f4957]">{winner}</p>
              </div>
              <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3">
                <div className="space-y-1">
                  <BarRow value={leftPercent} tone="left" />
                  <BarRow value={rightPercent} tone="right" />
                </div>
                <p className="min-w-20 text-right text-xs text-[#2f4957]">{(leftPercent * 100).toFixed(1)}%</p>
                <p className="min-w-20 text-right text-xs text-[#2f4957]">{(rightPercent * 100).toFixed(1)}%</p>
              </div>
            </div>
          );
        })}
      </div>

      <footer className="mt-3 grid grid-cols-2 gap-3 text-xs text-[#4f6774]">
        <p>
          {leftLabel} sampled moves: <span className="font-semibold text-[#2b4351]">{leftCounts.total}</span>
        </p>
        <p>
          {rightLabel} sampled moves: <span className="font-semibold text-[#2b4351]">{rightCounts.total}</span>
        </p>
      </footer>
    </article>
  );
}

function BarRow({ value, tone }: { value: number; tone: "left" | "right" }) {
  return (
    <div className="h-2 rounded-full bg-[#e8e3d9]">
      <div
        className={tone === "left" ? "h-2 rounded-full bg-[#1f637d]" : "h-2 rounded-full bg-[#b46e35]"}
        style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }}
      />
    </div>
  );
}

function compareHigherIsBetter(left: number, right: number): string {
  if (Math.abs(left - right) < 1e-6) {
    return "tie";
  }
  return left > right ? "A higher" : "B higher";
}
