import type { CSSProperties } from "react";
const paths = {
  user: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-2a8 8 0 0 1 16 0v2",
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  search: "M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  refresh: "M20 7v5h-5 M4 17v-5h5 M5.6 6a8 8 0 0 1 13 0L20 8 M4 16l1.4 2a8 8 0 0 0 13-1",
  arrow: "M4 12h16 M14 6l6 6-6 6", back: "M20 12H4 M10 6l-6 6 6 6",
  compare: "M4 4h6v16H4z M14 4h6v16h-6z", close: "M6 6l12 12 M6 18L18 6",
  check: "M5 12l4 4L19 6", alert: "M12 3L2 21h20L12 3z M12 9v5 M12 17v.1",
  file: "M14 2H5v20h14V7l-5-5z M14 2v5h5 M8 12h8 M8 16h8",
  chevron: "M9 5l7 7-7 7", copy: "M9 9h12v12H9z M15 9V3H3v12h6",
  play: "M7 4v16l14-8L7 4z", pause: "M7 4v16 M17 4v16",
  first: "M5 4v16 M19 5l-8 7 8 7", last: "M19 4v16 M5 5l8 7-8 7",
  flip: "M4 8h15l-4-4 M20 16H5l4 4", chart: "M3 3v18h18 M6 15l5-6 4 4 6-9",
  clock: "M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  sliders: "M4 7h10 M18 7h2 M14 4.5v5 M4 12h4 M12 12h8 M8 9.5v5 M4 17h9 M17 17h3 M13 14.5v5",
} as const;
export type IconName = keyof typeof paths;
export function Icon({ name, size = 18, style }: { name: IconName; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>;
}
