import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

export interface SeriesDef {
  label: string;
  color: string;
  fill?: boolean;
  width?: number;
}

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
 */
export function UPlotChart({ x, series, ys, height = 180, yLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);

  useEffect(() => {
    if (!ref.current || x.length === 0) return;
    const fmtVal = (raw: number): string =>
      Math.abs(raw) >= 1e6
        ? (raw / 1e6).toFixed(1) + "M"
        : Math.abs(raw) >= 1e3
          ? (raw / 1e3).toFixed(1) + "k"
          : String(Math.round(raw * 100) / 100);

    const opts: uPlot.Options = {
      width: ref.current.clientWidth,
      height,
      cursor: { points: { show: false } },
      axes: [
        {
          stroke: "#5a6870",
          grid: { show: true, stroke: "#232b36", width: 1 },
          ticks: { show: true, stroke: "#232b36" },
          labelSize: 9,
          labelFont: "Geist Mono, monospace",
        },
        {
          stroke: "#5a6870",
          grid: { show: true, stroke: "#232b36", width: 1 },
          label: yLabel,
          labelSize: 9,
          labelFont: "Geist Mono, monospace",
          values: (_self: uPlot, ticks: number[]) => ticks.map(fmtVal),
        },
      ],
      scales: { x: { time: false } },
      legend: { show: series.length > 1, live: false },
      series: [
        {},
        ...series.map((s) => ({
          label: s.label,
          stroke: s.color,
          width: s.width ?? 1.6,
          fill: s.fill ? s.color + "22" : undefined,
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
  }, [x, series, ys, height, yLabel]);

  return <div ref={ref} className="w-full" />;
}
