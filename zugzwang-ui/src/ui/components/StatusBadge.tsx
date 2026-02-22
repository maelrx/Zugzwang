type StatusBadgeProps = {
  label: string;
  tone?: "neutral" | "info" | "success" | "warning" | "error";
};

export function StatusBadge({ label, tone = "neutral" }: StatusBadgeProps) {
  return (
    <span className={["inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em]", toneClassName(tone)].join(" ")}>
      {label}
    </span>
  );
}

function toneClassName(tone: StatusBadgeProps["tone"]): string {
  if (tone === "success") {
    return "border-[var(--color-success-border)] bg-[var(--color-success-bg)] text-[var(--color-success-text)]";
  }
  if (tone === "warning") {
    return "border-[var(--color-warning-border)] bg-[var(--color-warning-bg)] text-[var(--color-warning-text)]";
  }
  if (tone === "error") {
    return "border-[var(--color-error-border)] bg-[var(--color-error-bg)] text-[var(--color-error-text)]";
  }
  if (tone === "info") {
    return "border-[var(--color-info-border)] bg-[var(--color-info-bg)] text-[var(--color-info-text)]";
  }
  return "border-[var(--color-neutral-border)] bg-[var(--color-neutral-bg)] text-[var(--color-neutral-text)]";
}

