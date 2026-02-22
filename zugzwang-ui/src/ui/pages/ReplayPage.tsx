import { useParams } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Chessboard } from "react-chessboard";
import { useGame, useGameFrames } from "../../api/queries";
import { PageHeader } from "../components/PageHeader";

export function ReplayPage() {
  const params = useParams({ strict: false }) as { runId: string; gameNumber: string };
  const runId = params.runId;
  const gameNumber = Number.parseInt(params.gameNumber, 10);

  const gameQuery = useGame(runId, Number.isFinite(gameNumber) ? gameNumber : null);
  const framesQuery = useGameFrames(runId, Number.isFinite(gameNumber) ? gameNumber : null);
  const frames = framesQuery.data ?? [];
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAutoplay, setIsAutoplay] = useState(false);
  const [autoplayMs, setAutoplayMs] = useState(900);

  const safeIndex = Math.max(0, Math.min(currentIndex, Math.max(0, frames.length - 1)));
  const frame = frames[safeIndex];
  const selectedPly = frame?.ply_number ?? safeIndex;
  const selectedMoveMetrics = useMemo(
    () => extractMoveMetricsForPly(gameQuery.data?.moves ?? [], selectedPly),
    [gameQuery.data?.moves, selectedPly],
  );
  const lastMoveArrow = useMemo(() => buildMoveArrow(frame?.move_uci), [frame?.move_uci]);

  const moveLabels = useMemo(() => {
    const moves = gameQuery.data?.moves ?? [];
    return moves.map((rawMove, idx) => {
      const move = asRecord(rawMove);
      const decision = asRecord(move.move_decision);
      const san = typeof decision.move_san === "string" ? decision.move_san : null;
      const uci = typeof decision.move_uci === "string" ? decision.move_uci : null;
      return {
        key: `${idx}-${move.ply_number ?? idx + 1}`,
        ply: Number(move.ply_number ?? idx + 1),
        label: san || uci || "(unknown)",
      };
    });
  }, [gameQuery.data?.moves]);

  useEffect(() => {
    if (!isAutoplay || frames.length <= 1) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setCurrentIndex((prev) => {
        const max = Math.max(0, frames.length - 1);
        if (prev >= max) {
          setIsAutoplay(false);
          return prev;
        }
        return prev + 1;
      });
    }, autoplayMs);

    return () => window.clearInterval(intervalId);
  }, [autoplayMs, frames.length, isAutoplay]);

  return (
    <section>
      <PageHeader
        eyebrow="Replay"
        title={`${runId} / game ${Number.isFinite(gameNumber) ? gameNumber : "?"}`}
        subtitle="Interactive move-by-move replay with board state and per-ply telemetry."
      />

      {(gameQuery.isLoading || framesQuery.isLoading) && <p className="mb-3 text-sm text-[#4f6572]">Loading game replay...</p>}

      {(gameQuery.isError || framesQuery.isError) && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff1ef] px-3 py-2 text-sm text-[#8a3333]">
          Failed to load replay data.
        </p>
      )}

      <div className="mb-4 rounded-2xl border border-[#d9d1c5] bg-white/85 p-4">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <label htmlFor="ply-slider" className="text-sm font-semibold text-[#2a4352]">
            Ply
          </label>
          <input
            id="ply-slider"
            type="range"
            min={0}
            max={Math.max(0, frames.length - 1)}
            value={safeIndex}
            onChange={(event) => setCurrentIndex(Number(event.target.value))}
            className="w-full"
          />
          <span className="w-16 text-right text-sm text-[#44606f]">
            {safeIndex}/{Math.max(0, frames.length - 1)}
          </span>
          <button
            type="button"
            className="rounded-md border border-[#d8d0c4] bg-white px-2 py-1 text-xs text-[#2a4452]"
            onClick={() => {
              setIsAutoplay(false);
              setCurrentIndex((prev) => Math.max(0, prev - 1));
            }}
            disabled={safeIndex <= 0}
          >
            Prev
          </button>
          <button
            type="button"
            className="rounded-md border border-[#d8d0c4] bg-white px-2 py-1 text-xs text-[#2a4452]"
            onClick={() => {
              setIsAutoplay(false);
              setCurrentIndex((prev) => Math.min(Math.max(0, frames.length - 1), prev + 1));
            }}
            disabled={safeIndex >= Math.max(0, frames.length - 1)}
          >
            Next
          </button>
          <button
            type="button"
            className={[
              "rounded-md border px-2 py-1 text-xs",
              isAutoplay ? "border-[#1f637d] bg-[#1f637d] text-[#edf8fd]" : "border-[#d8d0c4] bg-white text-[#2a4452]",
            ].join(" ")}
            disabled={frames.length <= 1}
            onClick={() => setIsAutoplay((prev) => !prev)}
          >
            {isAutoplay ? "Pause" : "Autoplay"}
          </button>
          <button
            type="button"
            className="rounded-md border border-[#d8d0c4] bg-white px-2 py-1 text-xs text-[#2a4452]"
            onClick={() => {
              setIsAutoplay(false);
              setCurrentIndex(0);
            }}
            disabled={safeIndex === 0}
          >
            Reset
          </button>
          <label className="text-xs text-[#4f6471]">
            speed
            <select
              value={autoplayMs}
              onChange={(event) => setAutoplayMs(Number(event.target.value))}
              className="ml-1 rounded-md border border-[#d8d0c4] bg-white px-1.5 py-0.5 text-xs text-[#2a4452]"
            >
              <option value={1200}>slow</option>
              <option value={900}>normal</option>
              <option value={600}>fast</option>
            </select>
          </label>
        </div>

        <div className="grid gap-4 lg:grid-cols-[440px_1fr]">
          <article className="rounded-xl border border-[#e0d9ce] bg-[#f9f6f0] p-3">
            <div className="mx-auto w-full max-w-[420px]">
              <Chessboard
                options={{
                  id: "zugzwang-replay",
                  position: frame?.fen ?? "start",
                  boardOrientation: "white",
                  allowDragging: false,
                  allowDrawingArrows: true,
                  arrows: lastMoveArrow ? [lastMoveArrow] : [],
                  boardStyle: { width: "100%", maxWidth: "420px" },
                  darkSquareStyle: { backgroundColor: "#c4a877" },
                  lightSquareStyle: { backgroundColor: "#f2dfbf" },
                }}
              />
            </div>
          </article>

          <article className="rounded-xl border border-[#e0d9ce] bg-[#f9f6f0] p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-[#5d7280]">Frame</p>
            <p className="mt-2 text-sm text-[#284150]">FEN: {frame?.fen ?? "--"}</p>
            <p className="mt-1 text-sm text-[#284150]">SAN: {frame?.move_san ?? "--"}</p>
            <p className="mt-1 text-sm text-[#284150]">UCI: {frame?.move_uci ?? "--"}</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <MetricChip label="Tokens in" value={asText(selectedMoveMetrics.tokensInput)} />
              <MetricChip label="Tokens out" value={asText(selectedMoveMetrics.tokensOutput)} />
              <MetricChip label="Latency ms" value={asText(selectedMoveMetrics.latencyMs)} />
              <MetricChip label="Retries" value={asText(selectedMoveMetrics.retryCount)} />
              <MetricChip label="Parse ok" value={selectedMoveMetrics.parseOk ? "yes" : "no"} />
              <MetricChip label="Legal" value={selectedMoveMetrics.isLegal ? "yes" : "no"} />
              <MetricChip label="Cost USD" value={asCost(selectedMoveMetrics.costUsd)} />
              <MetricChip label="Model" value={selectedMoveMetrics.providerModel || "--"} />
            </div>
            <p className="mt-4 text-xs uppercase tracking-[0.14em] text-[#5d7280]">Raw response</p>
            <pre className="mt-2 max-h-[150px] overflow-auto rounded-md bg-white/90 p-2 font-['IBM_Plex_Mono'] text-xs text-[#2b4451]">
              {frame?.raw_response ?? "(none)"}
            </pre>
          </article>
        </div>
      </div>

      <div className="rounded-2xl border border-[#d9d1c5] bg-white/85 p-4">
        <p className="mb-3 text-sm font-semibold text-[#264251]">Moves</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {moveLabels.map((item, index) => (
            <button
              type="button"
              key={item.key}
              className={[
                "rounded-lg border px-2.5 py-1.5 text-left text-xs",
                item.ply === selectedPly
                  ? "border-[#1f637d] bg-[#1f637d] text-[#edf8fd]"
                  : "border-[#ded7cc] bg-[#f8f5ef] text-[#2f4957]",
              ].join(" ")}
              onClick={() => setCurrentIndex(index + 1)}
            >
              {item.ply}. {item.label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  return {};
}

function buildMoveArrow(moveUci: string | null | undefined): { startSquare: string; endSquare: string; color: string } | null {
  if (!moveUci || moveUci.length < 4) {
    return null;
  }
  const from = moveUci.slice(0, 2);
  const to = moveUci.slice(2, 4);
  if (!isSquare(from) || !isSquare(to)) {
    return null;
  }
  return { startSquare: from, endSquare: to, color: "#1f637d99" };
}

function isSquare(value: string): boolean {
  return /^[a-h][1-8]$/.test(value);
}

type MoveMetrics = {
  tokensInput: number;
  tokensOutput: number;
  latencyMs: number;
  retryCount: number;
  parseOk: boolean;
  isLegal: boolean;
  costUsd: number;
  providerModel: string;
};

function extractMoveMetricsForPly(moves: Record<string, unknown>[], ply: number): MoveMetrics {
  if (ply <= 0) {
    return emptyMoveMetrics();
  }

  const rawMove = moves.find((entry, idx) => Number(asRecord(entry).ply_number ?? idx + 1) === ply);
  if (!rawMove) {
    return emptyMoveMetrics();
  }

  const decision = asRecord(asRecord(rawMove).move_decision);
  return {
    tokensInput: asNumber(decision.tokens_input),
    tokensOutput: asNumber(decision.tokens_output),
    latencyMs: asNumber(decision.latency_ms),
    retryCount: asNumber(decision.retry_count),
    parseOk: asBoolean(decision.parse_ok),
    isLegal: asBoolean(decision.is_legal),
    costUsd: asNumber(decision.cost_usd),
    providerModel: typeof decision.provider_model === "string" ? decision.provider_model : "",
  };
}

function emptyMoveMetrics(): MoveMetrics {
  return {
    tokensInput: 0,
    tokensOutput: 0,
    latencyMs: 0,
    retryCount: 0,
    parseOk: false,
    isLegal: false,
    costUsd: 0,
    providerModel: "",
  };
}

function asNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function asBoolean(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return value.toLowerCase() === "true";
  }
  return false;
}

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[#ded7cb] bg-white/90 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[#6a7f8c]">{label}</p>
      <p className="mt-1 truncate text-xs font-semibold text-[#2b4552]">{value}</p>
    </div>
  );
}

function asText(value: number): string {
  if (!Number.isFinite(value)) {
    return "--";
  }
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(3);
}

function asCost(value: number): string {
  if (!Number.isFinite(value)) {
    return "--";
  }
  return value.toFixed(6);
}
