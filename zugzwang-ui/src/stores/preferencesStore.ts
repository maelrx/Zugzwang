import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type ThemePreference = "light";

type PreferencesState = {
  defaultProvider: string | null;
  defaultModel: string | null;
  autoEvaluate: boolean;
  notificationsEnabled: boolean;
  theme: ThemePreference;
  setDefaultProvider: (provider: string | null) => void;
  setDefaultModel: (model: string | null) => void;
  setAutoEvaluate: (enabled: boolean) => void;
  setNotificationsEnabled: (enabled: boolean) => void;
  setTheme: (theme: ThemePreference) => void;
};

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      defaultProvider: null,
      defaultModel: null,
      autoEvaluate: true,
      notificationsEnabled: true,
      theme: "light",
      setDefaultProvider: (provider) => set({ defaultProvider: provider }),
      setDefaultModel: (model) => set({ defaultModel: model }),
      setAutoEvaluate: (enabled) => set({ autoEvaluate: enabled }),
      setNotificationsEnabled: (enabled) => set({ notificationsEnabled: enabled }),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "zugzwang-preferences-v2",
      storage: createJSONStorage(() => localStorage),
      version: 1,
    },
  ),
);

