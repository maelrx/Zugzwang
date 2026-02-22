import type { GameDetailResponse } from "../../api/types";

type UnknownRecord = Record<string, unknown>;

export type MoveQualityCounts = {
  clean: number;
  recovered: number;
  illegal: number;
  parseFail: number;
  total: number;
};

const EMPTY_COUNTS: MoveQualityCounts = {
  clean: 0,
  recovered: 0,
  illegal: 0,
  parseFail: 0,
  total: 0,
};

export function aggregateMoveQuality(games: GameDetailResponse[]): MoveQualityCounts {
  const counts: MoveQualityCounts = { ...EMPTY_COUNTS };

  for (const game of games) {
    const moves = Array.isArray(game.moves) ? game.moves : [];
    for (const rawMove of moves) {
      const move = asRecord(rawMove);
      const moveDecision = asRecord(move.move_decision);
      const classification = classifyMove(moveDecision);
      counts[classification] += 1;
      counts.total += 1;
    }
  }

  return counts;
}

export function moveQualityPercentages(counts: MoveQualityCounts): Record<Exclude<keyof MoveQualityCounts, "total">, number> {
  const total = counts.total > 0 ? counts.total : 1;
  return {
    clean: counts.clean / total,
    recovered: counts.recovered / total,
    illegal: counts.illegal / total,
    parseFail: counts.parseFail / total,
  };
}

export function formatMoveQualityLabel(key: Exclude<keyof MoveQualityCounts, "total">): string {
  if (key === "parseFail") {
    return "Parse Fail";
  }
  if (key === "recovered") {
    return "Recovered";
  }
  if (key === "illegal") {
    return "Illegal";
  }
  return "Clean";
}

function classifyMove(decision: UnknownRecord): Exclude<keyof MoveQualityCounts, "total"> {
  const parseOk = toBoolean(decision.parse_ok);
  if (!parseOk) {
    return "parseFail";
  }

  const legal = toBoolean(decision.is_legal);
  if (!legal) {
    return "illegal";
  }

  const retryCount = toNumber(decision.retry_count) ?? 0;
  if (retryCount > 0) {
    return "recovered";
  }

  return "clean";
}

function asRecord(value: unknown): UnknownRecord {
  if (value && typeof value === "object") {
    return value as UnknownRecord;
  }
  return {};
}

function toBoolean(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return value.trim().toLowerCase() === "true";
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  return false;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}
