import { useCallback, useEffect, useRef, useState } from "react";
import type { Snapshot } from "./types";

const DATA_URL = "/data/data.json";

/** Read-only snapshot loader with light polling (realtime within snapshot cadence). */
export function useSnapshot(pollMs = 15000): {
  snap: Snapshot | null;
  loading: boolean;
  error: string | null;
  refreshedAt: number | null;
  reload: () => void;
} {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);
  const alive = useRef(true);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as Snapshot;
      if (!alive.current) return;
      setSnap(json);
      setRefreshedAt(Date.now());
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
    setLoading(true);
    load();
  }, [load]);

  return { snap, loading, error, refreshedAt, reload };
}
