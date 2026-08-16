#!/usr/bin/env python3
import argparse
import re
from datetime import date
from pathlib import Path

root = Path(__file__).resolve().parents[1]
adr_dir = root / "docs/adr"
parser = argparse.ArgumentParser()
parser.add_argument("--title", required=True)
args = parser.parse_args()
ids = []
for p in adr_dir.glob("ADR-[0-9][0-9][0-9]-*.md"):
    ids.append(int(p.name[4:7]))
num = max(ids, default=0) + 1
slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")
path = adr_dir / f"ADR-{num:03d}-{slug}.md"
tpl = (adr_dir / "ADR-TEMPLATE.md").read_text(encoding="utf-8")
tpl = (
    tpl.replace("ADR-XXX", f"ADR-{num:03d}")
    .replace("Título", args.title)
    .replace('date: "YYYY-MM-DD"', f'date: "{date.today().isoformat()}"')
)
path.write_text(tpl, encoding="utf-8")
print(path.relative_to(root))
