import { useEffect, useRef } from "react";
import { Chessground } from "chessground";
import type { Api } from "chessground/api";
import type { Color, Key } from "chessground/types";
import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

interface Props {
  fen: string | null;
  lastUci: string | null;
  /** interactive mode: legal-ish move dests shown */
  viewOnly?: boolean;
}

/** Chessground replay board driven by FEN snapshots (no game logic state). */
export function Board({ fen, lastUci, viewOnly = true }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const api = useRef<Api | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    api.current = Chessground(ref.current, {
      viewOnly: true,
      animation: { enabled: true, duration: 220 },
      drawable: { enabled: false, visible: false },
      coordinates: true,
    });
    return () => {
      api.current?.destroy();
      api.current = null;
    };
  }, []);

  useEffect(() => {
    if (!api.current || !fen) return;
    const board = fen.split(" ")[0];
    const turn = fen.split(" ")[1] === "b" ? "black" : "white";
    const last: Key[] | undefined = lastUci
      ? [lastUci.slice(0, 2) as Key, lastUci.slice(2, 4) as Key]
      : undefined;
    // NOTE: chessground parses the FEN string itself; no manual piece map
    // needed (a previous manual map was dead code with a missing file
    // increment — removed rather than fixed).
    api.current.set({
      fen: board,
      turnColor: turn as Color,
      lastMove: last,
      highlight: { lastMove: true, check: false },
      check: undefined,
      movable: { free: false, color: undefined, showDests: false, dests: undefined },
      selectable: { enabled: !viewOnly },
    });
  }, [fen, lastUci, viewOnly]);

  return <div ref={ref} className="aspect-square w-full overflow-hidden rounded-md" role="img" aria-label="Tabuleiro de xadrez" />;
}
