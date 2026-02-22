import { useParams } from "@tanstack/react-router";
import { useMemo, useState } from "react";
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

  const safeIndex = Math.max(0, Math.min(currentIndex, Math.max(0, frames.length - 1)));
  const frame = frames[safeIndex];

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

  return (
    <section>
      <PageHeader
        eyebrow="Replay"
        title={`${runId} / game ${Number.isFinite(gameNumber) ? gameNumber : "?"}`}
        subtitle="Move-by-move replay scaffold. Board rendering with react-chessboard is planned for the next milestone."
      />

      {(gameQuery.isLoading || framesQuery.isLoading) && <p className="mb-3 text-sm text-[#4f6572]">Loading game replay...</p>}

      {(gameQuery.isError || framesQuery.isError) && (
        <p className="mb-3 rounded-lg border border-[#cf8f8f] bg-[#fff1ef] px-3 py-2 text-sm text-[#8a3333]">
          Failed to load replay data.
        </p>
      )}

      <div className="mb-4 rounded-2xl border border-[#d9d1c5] bg-white/85 p-4">
        <div className="mb-3 flex items-center gap-3">
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
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <article className="rounded-xl border border-[#e0d9ce] bg-[#f9f6f0] p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-[#5d7280]">Frame</p>
            <p className="mt-2 text-sm text-[#284150]">FEN: {frame?.fen ?? "--"}</p>
            <p className="mt-1 text-sm text-[#284150]">SAN: {frame?.move_san ?? "--"}</p>
            <p className="mt-1 text-sm text-[#284150]">UCI: {frame?.move_uci ?? "--"}</p>
          </article>

          <article className="rounded-xl border border-[#e0d9ce] bg-[#f9f6f0] p-3">
            <p className="text-xs uppercase tracking-[0.14em] text-[#5d7280]">Raw response</p>
            <pre className="mt-2 max-h-[160px] overflow-auto rounded-md bg-white/90 p-2 font-['IBM_Plex_Mono'] text-xs text-[#2b4451]">
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
                index + 1 === safeIndex
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
