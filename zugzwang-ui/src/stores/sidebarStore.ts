import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type SidebarState = {
  collapsed: boolean;
  activeSection: "navigation" | "active-jobs";
  setCollapsed: (collapsed: boolean) => void;
  toggleCollapsed: () => void;
  setActiveSection: (section: "navigation" | "active-jobs") => void;
};

export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      collapsed: false,
      activeSection: "navigation",
      setCollapsed: (collapsed) => set({ collapsed }),
      toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),
      setActiveSection: (section) => set({ activeSection: section }),
    }),
    {
      name: "zugzwang-sidebar-v2",
      storage: createJSONStorage(() => localStorage),
      version: 1,
    },
  ),
);

