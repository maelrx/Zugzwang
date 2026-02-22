import { useEffect, useMemo, useRef, useState } from "react";
import type { JobLogLine } from "../../api/logs";

type LogTerminalProps = {
  lines: JobLogLine[];
  done: boolean;
};

type StreamFilter = {
  stdout: boolean;
  stderr: boolean;
  system: boolean;
};

const DEFAULT_FILTER: StreamFilter = {
  stdout: true,
  stderr: true,
  system: true,
};

export function LogTerminal({ lines, done }: LogTerminalProps) {
  const [filter, setFilter] = useState<StreamFilter>(DEFAULT_FILTER);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const filteredLines = useMemo(
    () =>
      lines.filter((line) => {
        if (line.stream === "stdout") {
          return filter.stdout;
        }
        if (line.stream === "stderr") {
          return filter.stderr;
        }
        return filter.system;
      }),
    [filter.stderr, filter.stdout, filter.system, lines],
  );

  useEffect(() => {
    if (!autoScroll) {
      return;
    }
    if (!scrollRef.current) {
      return;
    }
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [autoScroll, filteredLines.length]);

  return (
    <div className="overflow-hidden rounded-2xl border border-[#d9d1c5] bg-[#1b2329]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#29343c] px-4 py-2 text-xs uppercase tracking-[0.14em] text-[#a6bac7]">
        <span>Live log stream</span>
        <div className="flex flex-wrap items-center gap-2">
          <FilterButton label="stdout" active={filter.stdout} onClick={() => setFilter((prev) => ({ ...prev, stdout: !prev.stdout }))} />
          <FilterButton label="stderr" active={filter.stderr} onClick={() => setFilter((prev) => ({ ...prev, stderr: !prev.stderr }))} />
          <FilterButton label="system" active={filter.system} onClick={() => setFilter((prev) => ({ ...prev, system: !prev.system }))} />
          <button
            type="button"
            className={[
              "rounded-md border px-2 py-1 text-[10px] font-semibold",
              autoScroll ? "border-[#22759a] bg-[#22759a] text-[#eff8ff]" : "border-[#506573] bg-transparent text-[#c6d8e2]",
            ].join(" ")}
            onClick={() => setAutoScroll((prev) => !prev)}
          >
            {autoScroll ? "Auto-scroll on" : "Auto-scroll off"}
          </button>
          <span className="rounded-md border border-[#4d5f6b] px-2 py-1 text-[10px]">{done ? "done" : "streaming"}</span>
        </div>
      </div>

      <div ref={scrollRef} className="max-h-[420px] overflow-auto px-4 py-3 font-['IBM_Plex_Mono'] text-xs leading-relaxed">
        {filteredLines.length === 0 && <p className="text-[#93a5b1]">No logs for selected filters.</p>}
        {filteredLines.map((line, index) => (
          <p key={`${line.stream}-${index}`} className={lineClassName(line.stream)}>
            <span className="mr-2 inline-block min-w-16 text-[#84a6ba]">[{line.stream}]</span>
            <span>{line.text}</span>
          </p>
        ))}
      </div>
    </div>
  );
}

function FilterButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      className={[
        "rounded-md border px-2 py-1 text-[10px] font-semibold",
        active ? "border-[#26779b] bg-[#26779b] text-[#ecf7ff]" : "border-[#4d5f6b] bg-transparent text-[#c4d5df]",
      ].join(" ")}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function lineClassName(stream: JobLogLine["stream"]): string {
  if (stream === "stderr") {
    return "mb-1 text-[#ffb2ab]";
  }
  if (stream === "system") {
    return "mb-1 text-[#9ec3d7]";
  }
  return "mb-1 text-[#d9e5ed]";
}

