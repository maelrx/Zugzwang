import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    // COOP/COEP so the multithreaded WASM flavor works in dev when the
    // browser reports crossOriginIsolated. Harmless for the single flavor.
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
    proxy: {
      // snapshot read-only do workspace (gerado por scripts/build_readonly_viewer.py)
      "/data": {
        target: "http://127.0.0.1:4173",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/data/, ""),
      },
    },
  },
});
