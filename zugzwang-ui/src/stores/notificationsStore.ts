import { create } from "zustand";

export type ToastTone = "info" | "success" | "warning" | "error";

export type ToastItem = {
  id: string;
  title: string;
  message: string;
  tone: ToastTone;
  linkTo?: string;
  linkLabel?: string;
  createdAt: number;
};

type NotificationsState = {
  toasts: ToastItem[];
  pushToast: (payload: Omit<ToastItem, "id" | "createdAt">) => void;
  dismissToast: (id: string) => void;
  clearToasts: () => void;
};

const MAX_TOASTS = 3;

export const useNotificationStore = create<NotificationsState>()((set) => ({
  toasts: [],
  pushToast: (payload) =>
    set((state) => {
      const id = `toast-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
      const next = [{ ...payload, id, createdAt: Date.now() }, ...state.toasts];
      return { toasts: next.slice(0, MAX_TOASTS) };
    }),
  dismissToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    })),
  clearToasts: () => set({ toasts: [] }),
}));
