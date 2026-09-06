import type { CSSProperties } from "react";
import type { TextureId } from "@/lib/appearance";

/**
 * Paper textures as self-contained SVG feTurbulence tiles (data URIs).
 * Chosen over live CSS/SVG filters and over binary texture packs: zero
 * dependencies, resolution-independent tiles, license-free, no network fetch,
 * and no Safari repaint issues of filter-on-live-DOM (Codrops / CSS-Tricks
 * "Grainy Gradients" recipe). Blend mode and opacity differ per theme group:
 * dark surfaces take a neutral overlay grain, light "paper" surfaces take a
 * multiply speckle, and the linen variant uses soft-light so the relief reads.
 */
export interface TextureDef {
  id: TextureId;
  label: string;
  uri: string;
  tile: number;
  dark: { blend: CSSProperties["mixBlendMode"]; opacity: number };
  light: { blend: CSSProperties["mixBlendMode"]; opacity: number };
}

const GRAY_POST = "<feColorMatrix type='saturate' values='0'/><feComponentTransfer><feFuncR type='linear' slope='0.55' intercept='0.22'/><feFuncG type='linear' slope='0.55' intercept='0.22'/><feFuncB type='linear' slope='0.55' intercept='0.22'/><feFuncA type='linear' slope='0' intercept='1'/></feComponentTransfer>";

const toUri = (svg: string): string => `data:image/svg+xml,${encodeURIComponent(svg)}`;

const NOISE = (freq: string, octaves: number, seed: number, size: number, post: string): string =>
  `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'><filter id='n' x='0' y='0' width='100%' height='100%'><feTurbulence type='fractalNoise' baseFrequency='${freq}' numOctaves='${octaves}' seed='${seed}' stitchTiles='stitch'/>${post}</filter><rect width='${size}' height='${size}' filter='url(#n)'/></svg>`;

const LINEN = (size: number): string =>
  `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'><filter id='n' x='0' y='0' width='100%' height='100%'><feTurbulence type='fractalNoise' baseFrequency='0.045' numOctaves='5' seed='5' stitchTiles='stitch'/><feDiffuseLighting lighting-color='white' surfaceScale='1.6' diffuseConstant='1.08'><feDistantLight azimuth='235' elevation='62'/></feDiffuseLighting></filter><rect width='${size}' height='${size}' filter='url(#n)'/></svg>`;

export const TEXTURES: Record<TextureId, TextureDef> = {
  paper: {
    id: "paper",
    label: "Papel",
    uri: toUri(NOISE("0.8", 4, 7, 240, GRAY_POST)),
    tile: 240,
    dark: { blend: "overlay", opacity: 0.16 },
    light: { blend: "multiply", opacity: 0.2 },
  },
  fiber: {
    id: "fiber",
    label: "Fibra",
    uri: toUri(NOISE("0.011 0.17", 4, 11, 260, GRAY_POST)),
    tile: 260,
    dark: { blend: "overlay", opacity: 0.2 },
    light: { blend: "multiply", opacity: 0.22 },
  },
  linen: {
    id: "linen",
    label: "Linho",
    uri: toUri(LINEN(300)),
    tile: 300,
    dark: { blend: "soft-light", opacity: 0.5 },
    light: { blend: "soft-light", opacity: 0.38 },
  },
  grain: {
    id: "grain",
    label: "Grão",
    uri: toUri(NOISE("1.1", 2, 3, 180, GRAY_POST)),
    tile: 180,
    dark: { blend: "overlay", opacity: 0.13 },
    light: { blend: "multiply", opacity: 0.14 },
  },
  none: {
    id: "none",
    label: "Nenhuma",
    uri: "",
    tile: 0,
    dark: { blend: "normal", opacity: 0 },
    light: { blend: "normal", opacity: 0 },
  },
};

export const TEXTURE_ORDER: TextureId[] = ["paper", "fiber", "linen", "grain", "none"];
