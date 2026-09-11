import { useCallback, useEffect, useRef, useState } from "react";
import { loadBundle, type CognitiveSnapshot } from "./cognitive";

const COGNITIVE_URL = "/data/cognitive.json";

/** Post-hoc cognitive bundle loader: dead data only, no engine, no writes. */
export function useCognitiveBundle(pollMs = 15000): {
  snapshots: CognitiveSnapshot[] | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
} {
  const [snapshots, setSnapshots] = useState<CognitiveSnapshot[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${COGNITIVE_URL}?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: unknown = await res.json();
      if (!alive.current) return;
      setSnapshots(loadBundle(json));
      setError(null);
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (alive.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    // Fetch-on-mount + poll: setState-in-effect is inherent to data loading.
    // eslint-disable-next-line react/set-state-in-effect
    load();
    const timer = pollMs > 0 ? window.setInterval(load, pollMs) : undefined;
    return () => {
      alive.current = false;
      if (timer) window.clearInterval(timer);
    };
  }, [pollMs, load]);

  const reload = useCallback(() => {
    load();
  }, [load]);

  return { snapshots, loading, error, reload };
}
