import type { MoveQualityCounts } from "../lib/moveQuality";
import { formatMoveQualityLabel, moveQualityPercentages } from "../lib/moveQuality";

type MoveQualityDistributionCardProps = {
  title: string;
  subtitle: string;
  counts: MoveQualityCounts;
};

const ORDER: Array<Exclude<keyof MoveQualityCounts, "total">> = ["clean", "recovered", "illegal", "parseFail"];

export function MoveQualityDistributionCard({ title, subtitle, counts }: MoveQualityDistributionCardProps) {
  const rates = moveQualityPercentages(counts);

  return (
    <article className="rounded-2xl border border-[#ddd5c8] bg-white/85 p-4">
      <header className="mb-3">
        <h4 className="text-sm font-semibold text-[#264351]">{title}</h4>
        <p className="mt-1 text-xs text-[#576d7a]">{subtitle}</p>
        <p className="mt-2 text-xs text-[#4f6774]">Sampled moves: {counts.total}</p>
      </header>

      <div className="space-y-2">
        {ORDER.map((key) => {
          const percent = rates[key];
          const absolute = counts[key];
          return (
            <div key={key} className="rounded-md border border-[#eee8dd] bg-[#faf7f1] px-2.5 py-2">
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-[#2b4351]">{formatMoveQualityLabel(key)}</p>
                <p className="text-xs text-[#2f4957]">
                  {absolute} ({(percent * 100).toFixed(1)}%)
                </p>
              </div>
              <div className="h-2 rounded-full bg-[#e8e3d9]">
                <div className={barToneClass(key)} style={{ width: `${Math.max(0, Math.min(100, percent * 100))}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function barToneClass(key: Exclude<keyof MoveQualityCounts, "total">): string {
  if (key === "clean") {
    return "h-2 rounded-full bg-[#5ea97e]";
  }
  if (key === "recovered") {
    return "h-2 rounded-full bg-[#cf9a4a]";
  }
  if (key === "illegal") {
    return "h-2 rounded-full bg-[#cf704e]";
  }
  return "h-2 rounded-full bg-[#bf4d4d]";
}
