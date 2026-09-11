#!/usr/bin/env python
"""Multi-workspace merge for the viewer-next webui.

Builds a read-only snapshot per workspace (main + Luna + Gemini runs),
merges the runs arrays (dedupe by run id), enriches titles/tags,
recomputes the summary and publishes data.json atomically.
The webui polls every 15s, so games update live.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import time

REPO = pathlib.Path("/home/maelrx/Documents/ChatGPT/Zugzwang")
OUT = pathlib.Path("/home/maelrx/Documents/ChatGPT/Zugzwang-webui-appearance/viewer-next/public/data")
TMP = pathlib.Path("/tmp/zg-merge")

WORKSPACES = [
    ("main", REPO / ".zugzwang", "Zugzwang Base"),
    ("gemini-01-tactical-memory", pathlib.Path("/tmp/gemini-ws-1/.zugzwang"), "Gemini 3.8 Flash Low · Tactical Memory v2"),
    ("gemini-02-king-safety", pathlib.Path("/tmp/gemini-ws-2/.zugzwang"), "Gemini 3.8 Flash Low · King Safety Prophylaxis v2"),
    ("gemini-03-tactical-guardian", pathlib.Path("/tmp/gemini-ws-3/.zugzwang"), "Gemini 3.8 Flash Low · Tactical Guardian v2"),
    ("luna-tactical-memory", pathlib.Path("/tmp/luna-ws-5/.zugzwang"), "LUNA high · Vitória Xeque-mate [Tactical Memory]"),
    ("luna-guard", pathlib.Path("/tmp/luna-ws-1/.zugzwang"), "LUNA high · Tactical Guardian (+5.00)"),
    ("luna-deep-history", pathlib.Path("/tmp/luna-ws-2/.zugzwang"), "LUNA high · Deep History"),
    ("luna-sentinel-reply", pathlib.Path("/tmp/luna-ws-3/.zugzwang"), "LUNA high · Sentinel Reply"),
    ("luna-rich-survival", pathlib.Path("/tmp/luna-ws-4/.zugzwang"), "LUNA high · Rich Survival"),
    ("xpl-deepseek-1", pathlib.Path("/tmp/xpl-full-ws-1/.zugzwang"), "DeepSeek v4 Flash · Full Game 01"),
    ("xpl-deepseek-2", pathlib.Path("/tmp/xpl-full-ws-2/.zugzwang"), "DeepSeek v4 Flash · Full Game 02"),
    ("xpl-deepseek-3", pathlib.Path("/tmp/xpl-full-ws-3/.zugzwang"), "DeepSeek v4 Flash · Full Game 03"),
    ("luna-fast-01-tactical-memory", pathlib.Path("/tmp/luna-fast-ws-1/.zugzwang"), "LUNA high fast · Tactical Memory (ZGW-0113)"),
    ("luna-fast-02-king-safety", pathlib.Path("/tmp/luna-fast-ws-2/.zugzwang"), "LUNA high fast · King Safety Prophylaxis (ZGW-0113)"),
    ("luna-fast-03-tactical-guardian", pathlib.Path("/tmp/luna-fast-ws-3/.zugzwang"), "LUNA high fast · Tactical Guardian (ZGW-0113)"),
]
PREFIX = "window.ZUGZWANG_DATA = "


def build_one(tag: str, ws: pathlib.Path, friendly_name: str) -> dict | None:
    if not (ws / "state.db").exists():
        return None
    out_path = TMP / f"data-{tag}.js"
    try:
        subprocess.run(
            [
                str(REPO / ".venv/bin/python"),
                str(REPO / "scripts/build_readonly_viewer.py"),
                "--workspace", str(ws.parent),
                "--output", str(out_path),
                "--limit", "60",
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError) as e:
        return None
    try:
        text = out_path.read_text(encoding="utf-8").strip()
        body = text[len(PREFIX):] if text.startswith(PREFIX) else text
        data = json.loads(body.rstrip().rstrip(";"))
        for r in data.get("runs", []):
            r["workspaceTag"] = tag
            if not r.get("experiment") or r.get("experiment") == "Zugzwang run":
                r["experiment"] = friendly_name
            if not r.get("experimentName"):
                r["experimentName"] = friendly_name
        return data
    except Exception:
        return None


def sync_once():
    TMP.mkdir(parents=True, exist_ok=True)
    merged_runs: list[dict] = []
    seen: set[str] = set()
    for tag, ws, friendly in WORKSPACES:
        snap = build_one(tag, ws, friendly)
        if not snap:
            continue
        for run in snap.get("runs", []):
            rid = str(run.get("id") or "")
            if rid and rid in seen:
                continue
            seen.add(rid)
            merged_runs.append(run)
    if merged_runs:
        # Sort so running runs and high priority runs appear at the top
        def sort_key(r):
            st = r.get("status", "")
            # running first, then completed, then others
            prio = 0 if st == "RUNNING" else 1 if st == "COMPLETED" else 2
            # latest activity
            at = r.get("startedAt") or ""
            return (prio, at)
        merged_runs.sort(key=lambda r: (0 if r.get("status") == "RUNNING" else 1, r.get("startedAt", "")), reverse=True)

        summary = {"total": len(merged_runs)}
        for st in ("RUNNING", "COMPLETED", "FAILED", "CANCELLED"):
            summary[st.lower()] = sum(1 for r in merged_runs if r.get("status") == st)
        doc = {
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "workspace": "multi (main + luna + gemini live)",
            "readOnly": True,
            "runs": merged_runs,
            "summary": summary,
        }
        tmp_file = OUT / ".data.json.tmp"
        tmp_file.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        tmp_file.replace(OUT / "data.json")
        print(f"[{time.strftime('%X')}] Published {len(merged_runs)} runs to {OUT / 'data.json'}")


def main():
    while True:
        try:
            sync_once()
        except Exception as e:
            print("Sync error:", e)
        time.sleep(12)


if __name__ == "__main__":
    main()
