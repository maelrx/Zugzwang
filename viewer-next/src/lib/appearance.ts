import { useSyncExternalStore } from "react";

export type ThemeId = "dark" | "dark-deep" | "light";
export type TextureId = "paper" | "fiber" | "linen" | "grain" | "none";

export interface Appearance {
  theme: ThemeId;
  texture: TextureId;
  /** multiplier applied to every font size (0.9–1.3) */
  fontScale: number;
}

export const THEMES: { id: ThemeId; label: string; bg: string; ac: string }[] = [
  { id: "dark", label: "Escuro", bg: "#0b0e12", ac: "#e8a865" },
  { id: "dark-deep", label: "Profundo", bg: "#080a0d", ac: "#ae7e4c" },
  { id: "light", label: "Claro", bg: "#eef1f4", ac: "#a86a24" },
];

export const FONT_SCALES: { value: number; label: string }[] = [
  { value: 0.9, label: "90%" },
  { value: 1, label: "100%" },
  { value: 1.15, label: "115%" },
  { value: 1.3, label: "130%" },
];

const STORAGE_KEY = "zg-appearance";
const CHANGE_EVENT = "zg-appearance";
const DEFAULTS: Appearance = { theme: "dark", texture: "paper", fontScale: 1 };

let current: Appearance = DEFAULTS;

function coerce(raw: unknown): Appearance {
  const v = (raw ?? {}) as Partial<Appearance>;
  const theme = THEMES.some(t => t.id === v.theme) ? v.theme! : DEFAULTS.theme;
  const texture: TextureId = (["paper", "fiber", "linen", "grain", "none"] as const).includes(v.texture as TextureId)
    ? v.texture!
    : DEFAULTS.texture;
  const known = FONT_SCALES.find(f => f.value === v.fontScale);
  return { theme, texture, fontScale: known ? known.value : DEFAULTS.fontScale };
}

export function loadAppearance(): Appearance {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    current = raw ? coerce(JSON.parse(raw)) : DEFAULTS;
  } catch {
    current = DEFAULTS;
  }
  return current;
}

/** Applies settings to <html> and persists them; call once before React mounts and on every change. */
export function applyAppearance(next: Appearance): void {
  current = coerce(next);
  const el = document.documentElement;
  el.dataset.theme = current.theme;
  el.dataset.texture = current.texture;
  el.style.setProperty("--fs-scale", String(current.fontScale));
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
  } catch {
    /* private mode / storage blocked → session-only */
  }
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
}

export function setAppearance(patch: Partial<Appearance>): void {
  applyAppearance({ ...current, ...patch });
}

export function onAppearance(listener: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, listener);
  return () => window.removeEventListener(CHANGE_EVENT, listener);
}

function subscribe(listener: () => void): () => void {
  return onAppearance(listener);
}

/** React binding: re-renders consumers whenever appearance changes. */
export function useAppearance(): Appearance {
  return useSyncExternalStore(subscribe, () => current, () => current);
}

/** Resolves a CSS custom property to a concrete color string (for canvas-based charts). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
