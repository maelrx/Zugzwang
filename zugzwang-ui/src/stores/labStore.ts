import { create } from "zustand";

type LabState = {
  selectedTemplatePath: string | null;
  selectedProvider: string | null;
  selectedModel: string | null;
  rawOverridesText: string;
  advancedOpen: boolean;
  setSelectedTemplatePath: (path: string | null) => void;
  setSelectedProvider: (provider: string | null) => void;
  setSelectedModel: (model: string | null) => void;
  setRawOverridesText: (text: string) => void;
  setAdvancedOpen: (open: boolean) => void;
  resetLabState: () => void;
};

const INITIAL_STATE = {
  selectedTemplatePath: null,
  selectedProvider: null,
  selectedModel: null,
  rawOverridesText: "",
  advancedOpen: false,
};

export const useLabStore = create<LabState>()((set) => ({
  ...INITIAL_STATE,
  setSelectedTemplatePath: (path) => set({ selectedTemplatePath: path }),
  setSelectedProvider: (provider) => set({ selectedProvider: provider }),
  setSelectedModel: (model) => set({ selectedModel: model }),
  setRawOverridesText: (text) => set({ rawOverridesText: text }),
  setAdvancedOpen: (open) => set({ advancedOpen: open }),
  resetLabState: () => set({ ...INITIAL_STATE }),
}));

