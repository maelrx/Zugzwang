#!/usr/bin/env bash
# Regen the viewer snapshot from the workspace DB and publish it to viewer-next/public/data.
# Runs detached; the app polls /data/data.json every 15s, so matches update live.
set -u
REPO=/home/maelrx/Documents/ChatGPT/Zugzwang
OUT=/home/maelrx/Documents/ChatGPT/Zugzwang-webui-appearance/viewer-next/public/data
mkdir -p "$OUT"
while true; do
  if (cd "$REPO" && uv run python scripts/build_readonly_viewer.py --workspace . >/dev/null 2>&1); then
    python3 - "$REPO/viewer/data.js" "$OUT/.data.json.tmp" <<'PY'
import sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip()
prefix = "window.ZUGZWANG_DATA = "
body = src[len(prefix):] if src.startswith(prefix) else src
pathlib.Path(sys.argv[2]).write_text(body.rstrip().rstrip(";"), encoding="utf-8")
PY
    mv "$OUT/.data.json.tmp" "$OUT/data.json"
  fi
  sleep 30
done
