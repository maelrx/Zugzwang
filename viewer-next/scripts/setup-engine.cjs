#!/usr/bin/env node
/** Copy Stockfish WASM flavors from node_modules into public/engine/.
 * Binaries are gitignored; run via `npm run setup:engine` (also predev/prebuild). */
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const src = path.join(root, "node_modules", "stockfish", "bin");
const dst = path.join(root, "public", "engine");

const FILES = [
  "stockfish-18-lite-single.js",
  "stockfish-18-lite-single.wasm",
  "stockfish-18-lite.js",
  "stockfish-18-lite.wasm",
];

fs.mkdirSync(dst, { recursive: true });
let missing = 0;
for (const f of FILES) {
  const from = path.join(src, f);
  if (!fs.existsSync(from)) {
    console.error(`missing ${f} — run npm install stockfish`);
    missing++;
    continue;
  }
  fs.copyFileSync(from, path.join(dst, f));
  console.log(`engine: ${f} -> public/engine/`);
}
process.exit(missing ? 1 : 0);
