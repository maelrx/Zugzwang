#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--id", required=True)
parser.add_argument("--title", required=True)
args = parser.parse_args()
if not re.fullmatch(r"[A-Z][A-Z0-9-]*-[0-9]{3}", args.id):
    raise SystemExit("ID must look like REP-001 or EXP-001")
out = root / "experiments" / args.id
out.mkdir(parents=True, exist_ok=False)
tpl = (root / "docs/research/EXPERIMENT_CARD_TEMPLATE.md").read_text(encoding="utf-8")
(out / "EXPERIMENT_CARD.md").write_text(
    tpl.replace("EXP-XXX", args.id).replace("Título", args.title), encoding="utf-8"
)
(out / "manifests").mkdir()
(out / "analysis").mkdir()
print(out.relative_to(root))
