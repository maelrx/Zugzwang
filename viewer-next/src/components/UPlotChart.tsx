import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { cssVar, onAppearance } from "@/lib/appearance";

export interface SeriesDef {
  label: string;
  /** CSS color, or "var:--color-name" resolved from the active theme at build time. */
  color: string;
  fill?: boolean;
  width?: number;
}

const resolveColor = (c: string): string => {
  if (!c.startsWith("var:")) return c;
  return cssVar(c.slice(4)) || "#888888";
};

interface Props {
  /** x values (shared domain, usually decision index or time). Must be ascending. */
  x: number[];
  series: SeriesDef[];
  ys: (number[] | null)[];
  height?: number;
  yLabel?: string;
}

/**
 * Thin React wrapper over uPlot (the engine behind Grafana panels): single
 * canvas, tiny footprint, handles thousands of points without layout thrash.
 * Rebuilt on appearance changes so axis/grid/series colors follow the theme.
 */
export function UPlotChart({ x, series, ys, height = 180, yLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const [themeTick, setThemeTick] = useState(0);

  useEffect(() => onAppearance(() => setThemeTick(t => t + 1)), []);

  useEffect(() => {
    if (!ref.current || x.length === 0) return;
    const fmtVal = (raw: number): string =>
      Math.abs(raw) >= 1e6
        ? (raw / 1e6).toFixed(1) + "M"
        : Math.abs(raw) >= 1e3
          ? (raw / 1e3).toFixed(1) + "k"
          : String(Math.round(raw * 100) / 100);

    const fs = Number(cssVar("--fs-scale")) || 1;
    const monoFont = (px: number) => `${Math.max(8, Math.round(px * fs))}px Geist Mono, monospace`;
    const axisStroke = cssVar("--color-faint") || "#5a6870";
    const gridStroke = cssVar("--color-line") || "#232b36";
    const opts: uPlot.Options = {
      width: ref.current.clientWidth,
      height,
      cursor: { points: { show: false } },
      axes: [
        {
          stroke: axisStroke,
          grid: { show: true, stroke: gridStroke, width: 1 },
          ticks: { show: true, stroke: gridStroke },
          labelSize: 9,
          labelFont: monoFont(9),
        },
        {
          stroke: axisStroke,
          grid: { show: true, stroke: gridStroke, width: 1 },
          label: yLabel,
          labelSize: 9,
          labelFont: monoFont(9),
          values: (_self: uPlot, ticks: number[]) => ticks.map(fmtVal),
        },
      ],
      scales: { x: { time: false } },
      legend: { show: series.length > 1, live: false },
      series: [
        {},
        ...series.map((s) => ({
          label: s.label,
          stroke: resolveColor(s.color),
          width: s.width ?? 1.6,
          fill: s.fill ? resolveColor(s.color) + "22" : undefined,
          points: { show: false },
        })),
      ],
    } as uPlot.Options;

    const data: uPlot.AlignedData = [
      Float64Array.from(x),
      ...ys.map((y) => Float64Array.from(y ?? [])),
    ];
    plot.current = new uPlot(opts, data, ref.current);

    const onResize = () => {
      if (plot.current && ref.current)
        plot.current.setSize({ width: ref.current.clientWidth, height });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      plot.current?.destroy();
      plot.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [x, series, ys, height, yLabel, themeTick]);

  return <div ref={ref} className="w-full" />;
}
