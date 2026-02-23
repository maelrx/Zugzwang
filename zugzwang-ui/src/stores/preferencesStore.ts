import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type ThemePreference = "light";
const DEFAULT_STOCKFISH_DEPTH = 12;
const MIN_STOCKFISH_DEPTH = 1;
const MAX_STOCKFISH_DEPTH = 30;

type PreferencesState = {
  defaultProvider: string | null;
  defaultModel: string | null;
  autoEvaluate: boolean;
  stockfishDepth: number;
  notificationsEnabled: boolean;
  theme: ThemePreference;
  setDefaultProvider: (provider: string | null) => void;
  setDefaultModel: (model: string | null) => void;
  setAutoEvaluate: (enabled: boolean) => void;
  setStockfishDepth: (depth: number) => void;
  setNotificationsEnabled: (enabled: boolean) => void;
  setTheme: (theme: ThemePreference) => void;
};

type PersistedPreferences = Pick<
  PreferencesState,
  "defaultProvider" | "defaultModel" | "autoEvaluate" | "stockfishDepth" | "notificationsEnabled" | "theme"
>;

const memoryStorage = createMemoryStorage();
const storage = createJSONStorage(() => resolveStorage());

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      defaultProvider: null,
      defaultModel: null,
      autoEvaluate: true,
      stockfishDepth: DEFAULT_STOCKFISH_DEPTH,
      notificationsEnabled: true,
      theme: "light",
      setDefaultProvider: (provider) => set({ defaultProvider: provider }),
      setDefaultModel: (model) => set({ defaultModel: model }),
      setAutoEvaluate: (enabled) => set({ autoEvaluate: enabled }),
      setStockfishDepth: (depth) =>
        set({
          stockfishDepth: clampDepth(depth),
        }),
      setNotificationsEnabled: (enabled) => set({ notificationsEnabled: enabled }),
      setTheme: (theme) => set({ theme: theme === "light" ? "light" : "light" }),
    }),
    {
      name: "zugzwang-preferences-v2",
      storage,
      version: 2,
      migrate: (persistedState, fromVersion) => {
        const snapshot = (persistedState as Partial<PersistedPreferences> | undefined) ?? {};
        if (fromVersion < 2) {
          return {
            defaultProvider: snapshot.defaultProvider ?? null,
            defaultModel: snapshot.defaultModel ?? null,
            autoEvaluate: snapshot.autoEvaluate ?? true,
            stockfishDepth: DEFAULT_STOCKFISH_DEPTH,
            notificationsEnabled: snapshot.notificationsEnabled ?? true,
            theme: "light",
          } satisfies PersistedPreferences;
        }
        return {
          defaultProvider: snapshot.defaultProvider ?? null,
          defaultModel: snapshot.defaultModel ?? null,
          autoEvaluate: snapshot.autoEvaluate ?? true,
          stockfishDepth: clampDepth(snapshot.stockfishDepth ?? DEFAULT_STOCKFISH_DEPTH),
          notificationsEnabled: snapshot.notificationsEnabled ?? true,
          theme: "light",
        } satisfies PersistedPreferences;
      },
    },
  ),
);

function clampDepth(depth: number): number {
  if (!Number.isFinite(depth)) {
    return DEFAULT_STOCKFISH_DEPTH;
  }
  return Math.min(MAX_STOCKFISH_DEPTH, Math.max(MIN_STOCKFISH_DEPTH, Math.round(depth)));
}

function resolveStorage(): Storage {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      const key = "__zugzwang-storage-check__";
      window.localStorage.setItem(key, "1");
      window.localStorage.removeItem(key);
      return window.localStorage;
    }
  } catch {
    // No-op: use in-memory fallback.
  }
  return memoryStorage;
}

function createMemoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => {
      data.clear();
    },
    getItem: (key) => {
      return data.has(key) ? data.get(key) ?? null : null;
    },
    key: (index) => {
      const keys = Array.from(data.keys());
      return keys[index] ?? null;
    },
    removeItem: (key) => {
      data.delete(key);
    },
    setItem: (key, value) => {
      data.set(key, String(value));
    },
  };
}
