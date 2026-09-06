/** Shared formatting helpers for the Match Desk. */

export const fmtNum = (n: number): string =>
  n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n);

export const fmtMs = (ms: number): string =>
  ms >= 60000
    ? (ms / 60000).toFixed(1) + " min"
    : ms >= 1000
      ? (ms / 1000).toFixed(1) + "s"
      : `${ms}ms`;

export function fmtDur(a: string | null, b: string | null): string {
  if (!a || !b) return "—";
  const ms = Date.parse(b) - Date.parse(a);
  if (ms < 0) return "—";
  const m = Math.floor(ms / 60000);
  return m >= 1 ? `${m}m ${Math.round((ms % 60000) / 1000)}s` : `${(ms / 1000).toFixed(0)}s`;
}
