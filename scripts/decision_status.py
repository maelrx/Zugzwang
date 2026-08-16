#!/usr/bin/env python3
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "PyYAML is required for this helper; inspect docs/decisions/DECISIONS.yaml manually.",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

root = Path(__file__).resolve().parents[1]
data = yaml.safe_load((root / "docs/decisions/DECISIONS.yaml").read_text(encoding="utf-8"))
print(f"Decision owner: {data['decision_owner']['name']}")
for gate in data["gates"]:
    marker = "✓" if gate["status"] == "accepted" else "·"
    print(f"{marker} {gate['id']}  {gate['status']:<9}  {gate['title']}  -> {gate['blocking']}")
