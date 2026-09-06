/**
 * Cognitive snapshot types and bundle loader (CB-WO-10, ZGW-0097).
 *
 * The causal viewer renders dead post-hoc data only: no fetch, no engine,
 * no write-back. A snapshot is produced by scripts/build_cognitive_viewer.py
 * (or a bundle.json export) and loaded from disk.
 */

export const SNAPSHOT_SCHEMA = "zgw.cognitive-snapshot/v1";

export interface CognitiveOperation {
  operation_id: string;
  tool: string;
  status: "PREPARED" | "COMMITTED" | "REJECTED" | "FAILED";
  error_code: string | null;
  artifact_verified?: boolean;
}

export interface CognitiveSnapshot {
  schema_version: string;
  decision_id: string;
  status: string;
  selected_action: string | null;
  next_round_ordinal: number;
  operations_settled: number;
  operations_open: string[];
  exposure_watermark: number;
  budget_balance: Record<string, { reserved: number; used: number; remaining: number }>;
  audit: {
    decision_id: string;
    status: string;
    selected_action: string | null;
    operations: CognitiveOperation[];
    observations: number;
    exposure_watermark: number;
    artifacts_verified: number;
    artifacts_failed: string[];
  };
  mode: "post_hoc";
  engine: null;
}

export function parseSnapshot(raw: unknown): CognitiveSnapshot {
  if (typeof raw !== "object" || raw === null) {
    throw new Error("snapshot is not an object");
  }
  const snap = raw as Record<string, unknown>;
  if (snap["schema_version"] !== SNAPSHOT_SCHEMA) {
    throw new Error(`unsupported snapshot schema: ${String(snap["schema_version"])}`);
  }
  if (snap["mode"] !== "post_hoc") {
    throw new Error("refusing live snapshot: viewer renders post-hoc data only");
  }
  if (snap["engine"] !== null && snap["engine"] !== undefined) {
    throw new Error("refusing snapshot with engine reference");
  }
  return snap as unknown as CognitiveSnapshot;
}

export function loadBundle(bundleJson: unknown): CognitiveSnapshot[] {
  // A bundle.json export carries decisions under `decisions` (or a single
  // snapshot at top level for the minimal CB-WO-10 path).
  if (typeof bundleJson !== "object" || bundleJson === null) {
    throw new Error("bundle is not an object");
  }
  const bundle = bundleJson as Record<string, unknown>;
  const decisions = bundle["decisions"];
  if (Array.isArray(decisions)) {
    return decisions.map((entry) => parseSnapshot(entry));
  }
  return [parseSnapshot(bundleJson)];
}
