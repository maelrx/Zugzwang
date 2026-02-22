type ProgressBarProps = {
  value: number;
  max: number;
  label?: string;
};

export function ProgressBar({ value, max, label }: ProgressBarProps) {
  const safeMax = max > 0 ? max : 1;
  const clampedValue = Math.max(0, Math.min(value, safeMax));
  const percent = (clampedValue / safeMax) * 100;

  return (
    <div>
      {label ? <p className="mb-1 text-xs text-[var(--color-text-secondary)]">{label}</p> : null}
      <div className="h-2.5 overflow-hidden rounded-full border border-[var(--color-border-default)] bg-[var(--color-surface-sunken)]">
        <div className="h-full bg-[var(--color-primary-600)] transition-[width] duration-300" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

