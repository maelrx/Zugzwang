import { create } from "zustand";

type CompareState = {
  selectedRunIds: string[];
  toggleRunSelection: (runId: string) => void;
  clearSelection: () => void;
  setSelection: (runIds: string[]) => void;
};

export const useCompareStore = create<CompareState>()((set) => ({
  selectedRunIds: [],
  toggleRunSelection: (runId) =>
    set((state) => {
      const alreadySelected = state.selectedRunIds.includes(runId);
      if (alreadySelected) {
        return { selectedRunIds: state.selectedRunIds.filter((id) => id !== runId) };
      }
      return { selectedRunIds: [...state.selectedRunIds, runId] };
    }),
  clearSelection: () => set({ selectedRunIds: [] }),
  setSelection: (runIds) => set({ selectedRunIds: [...new Set(runIds)] }),
}));

