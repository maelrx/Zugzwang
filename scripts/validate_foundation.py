#!/usr/bin/env python3
"""Validate the documentation-first Zugzwang foundation pack."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

# Build artifacts and virtual environments are not foundation content.
EXCLUDED_DIRS = {
    ".venv",
    ".ruff_cache",
    ".pytest_cache",
    ".pyright",
    ".git",
    "build",
    "dist",
    "__pycache__",
    ".hypothesis",
    "node_modules",
}

REQUIRED = [
    "README.md",
    "README.pt-BR.md",
    "START_HERE.md",
    "AGENTS.md",
    "docs/INDEX.md",
    "docs/decisions/DECISIONS.yaml",
    "docs/decisions/HUMAN_DECISION_GATES.pt-BR.md",
    "docs/roadmap/ROADMAP.md",
    "docs/research/SCIENTIFIC_FOUNDATIONS.md",
    "docs/architecture/MASTER_TECHNICAL_DESIGN.md",
    "docs/requirements/FUNCTIONAL_REQUIREMENTS.md",
    "docs/protocol/MANIFEST_SPEC.md",
    "schemas/experiment-manifest.schema.json",
]


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self, msg):
        self.passed.append(msg)


def parse_frontmatter(text: str):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    data = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip().strip("\"'")
    return data


def validate_required(r):
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            r.error(f"missing required file: {rel}")
    if not r.errors:
        r.ok("required files")


def _iter_files(root, pattern):
    for p in root.rglob(pattern):
        if any(part in EXCLUDED_DIRS for part in p.relative_to(root).parts):
            continue
        yield p


def validate_json(r):
    count = 0
    for p in _iter_files(ROOT, "*.json"):
        # ZGW-0085/#15: tsconfig*.json are JSONC toolchain configuration (not
        # foundation data); out of scope. node_modules is already excluded.
        if p.name.startswith("tsconfig"):
            continue
        try:
            json.loads(p.read_text(encoding="utf-8"))
            count += 1
        except Exception as e:
            r.error(f"invalid JSON {p.relative_to(ROOT)}: {e}")
    if count:
        r.ok(f"JSON parsed: {count}")


def validate_json_schemas_and_examples(r, strict=False):
    schema_dir = ROOT / "schemas"
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        r.warn("jsonschema unavailable; schema semantics/example validation skipped")
        if strict:
            r.error("strict mode requires jsonschema")
        return
    schemas = {}
    for p in schema_dir.glob("*.schema.json"):
        try:
            schema = json.loads(p.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[p.name] = schema
        except Exception as e:
            r.error(f"invalid JSON Schema {p.relative_to(ROOT)}: {e}")
    mappings = [
        ("experiment-manifest.schema.json", ROOT / "examples/experiments"),
        ("knowledge-packet.schema.json", ROOT / "examples/knowledge-packets"),
    ]
    try:
        import yaml
    except ImportError:
        yaml = None
    for schema_name, directory in mappings:
        if schema_name not in schemas or not directory.exists() or yaml is None:
            continue
        validator = Draft202012Validator(schemas[schema_name])
        for example in directory.glob("*.yaml"):
            try:
                data = yaml.safe_load(example.read_text(encoding="utf-8"))
                errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
                for error in errors:
                    r.error(
                        f"example/schema mismatch {example.relative_to(ROOT)} at {list(error.path)}: {error.message}"
                    )
            except Exception as e:
                r.error(f"cannot validate example {example.relative_to(ROOT)}: {e}")
    if schemas:
        r.ok(f"JSON Schemas checked: {len(schemas)}")


def validate_adrs(r):
    seen = set()
    count = 0
    for p in sorted((ROOT / "docs/adr").glob("ADR-[0-9][0-9][0-9]-*.md")):
        fm = parse_frontmatter(p.read_text(encoding="utf-8"))
        if not fm:
            r.error(f"ADR missing frontmatter: {p.relative_to(ROOT)}")
            continue
        ident = fm.get("id")
        if ident in seen:
            r.error(f"duplicate ADR id: {ident}")
        seen.add(ident)
        count += 1
        expected = p.name[:7]
        if ident != expected:
            r.error(f"ADR id/filename mismatch: {p.name} vs {ident}")
        if fm.get("status") not in {"proposed", "accepted", "deprecated", "superseded", "rejected"}:
            r.error(f"invalid ADR status {p.name}: {fm.get('status')}")
    if count < 45:
        r.error(f"expected at least 45 ADRs, found {count}")
    else:
        r.ok(f"ADRs validated: {count}")


def _tracked_skill_files(skill_root) -> tuple[list, list]:
    """Return (tracked-and-present, tracked-but-absent) versioned SKILL.md files.

    Absent tracked files happen under sparse checkout (REPOSITORY_STATUS:
    versioned skills may be hidden locally while the host catalog is on disk).
    """
    import subprocess

    try:
        listing = subprocess.run(
            ["git", "ls-files", "--", ".agents/skills"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    except Exception:
        return [], []
    tracked = sorted(
        ROOT / rel
        for rel in listing
        if rel.startswith(".agents/skills/") and rel.endswith("SKILL.md")
    )
    present = [p for p in tracked if p.is_file()]
    return present, [p for p in tracked if not p.is_file()]


def validate_skills(r):
    skill_root = ROOT / ".agents/skills"
    if not skill_root.exists():
        r.ok("skills catalog supplied by host; no vendored skills to validate")
        return
    # ZGW-0086: only the versioned catalog is validated. Host-injected skills
    # (symlinks or untracked copies; REPOSITORY_STATUS: never publish
    # absolute-path symlinks) are host configuration, not repo sources.
    dirs, hidden = _tracked_skill_files(skill_root)
    if not dirs and hidden:
        r.ok(
            f"versioned skills hidden by sparse checkout ({len(hidden)} tracked); "
            "host catalog not validated"
        )
        return
    if not dirs:
        # no git available: validate the real (non-symlink) catalog on disk
        dirs = sorted(p for p in skill_root.glob("*/SKILL.md") if not p.is_symlink())
    names = set()
    for p in dirs:
        fm = parse_frontmatter(p.read_text(encoding="utf-8"))
        if not fm:
            r.error(f"skill missing frontmatter: {p.relative_to(ROOT)}")
            continue
        name = fm.get("name")
        desc = fm.get("description")
        if name != p.parent.name:
            r.error(f"skill name/path mismatch: {p.relative_to(ROOT)}")
        if not desc or len(desc) < 30:
            r.error(f"skill description too weak: {p.relative_to(ROOT)}")
        if name in names:
            r.error(f"duplicate skill: {name}")
        names.add(name)
    if len(dirs) < 15:
        r.error(f"expected at least 15 skills, found {len(dirs)}")
    else:
        r.ok(f"skills validated: {len(dirs)}")


def validate_markdown_links(r):
    # Inline links only. Ignore URLs, anchors, mailto and image links.
    pat = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
    count = 0
    for p in _iter_files(ROOT, "*.md"):
        text = p.read_text(encoding="utf-8", errors="replace")
        for raw in pat.findall(text):
            target = raw.strip().split()[0].strip('<>"')
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = unquote(target).split("#", 1)[0]
            if not target:
                continue
            q = (p.parent / target).resolve()
            try:
                q.relative_to(ROOT.resolve())
            except ValueError:
                r.error(f"link escapes repo: {p.relative_to(ROOT)} -> {target}")
                continue
            if not q.exists():
                r.error(f"broken link: {p.relative_to(ROOT)} -> {target}")
            count += 1
    r.ok(f"local markdown links checked: {count}")


def validate_no_control_chars(r):
    bad = []
    binary_suffixes = {
        ".db",
        ".sqlite",
        ".sqlite3",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".zip",
    }
    for p in _iter_files(ROOT, "*"):
        if not p.is_file() or p.suffix.lower() in binary_suffixes | {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }:
            continue
        # ZGW-0086: runtime state (.zugzwang databases/WAL) is local evidence,
        # not documentation; never scan its bytes here.
        if ".zugzwang" in p.relative_to(ROOT).parts:
            continue
        data = p.read_bytes()
        for b in data:
            if b < 32 and b not in (9, 10, 13):
                bad.append(str(p.relative_to(ROOT)))
                break
    if bad:
        r.error("control characters in: " + ", ".join(bad[:20]))
    else:
        r.ok("no unexpected control characters")


def validate_decisions(r, strict=False):
    p = ROOT / "docs/decisions/DECISIONS.yaml"
    text = p.read_text(encoding="utf-8")
    ids = re.findall(r"^\s*- id: (GATE-[0-9]{3})\s*$", text, re.M)
    if len(ids) < 10:
        r.error(f"decision gate parse found only {len(ids)}")
    if len(ids) != len(set(ids)):
        r.error("duplicate decision gate IDs")
    selected_count = len(re.findall(r"selected_option:\s*(?!null)(\S+)", text))
    approved_count = len(re.findall(r"approved_by:\s*(?!null)(\S+)", text))
    if selected_count != approved_count:
        r.error(f"selected_option count ({selected_count}) != approved_by count ({approved_count})")
    # A selected option must have approved_by and accepted status; detailed YAML check if available.
    try:
        import yaml

        data = yaml.safe_load(text)
        for g in data.get("gates", []):
            if g.get("status") == "accepted":
                if (
                    not g.get("selected_option")
                    or not g.get("approved_by")
                    or not g.get("rationale")
                ):
                    r.error(f"accepted gate incomplete: {g.get('id')}")
            elif g.get("selected_option") or g.get("approved_by"):
                r.error(f"non-accepted gate has selection/signature: {g.get('id')}")
        r.ok(f"decision gates validated: {len(data.get('gates', []))}")
    except ImportError:
        r.warn("PyYAML unavailable; decision semantics only partially checked")
    if strict:
        pending = re.findall(r"status:\s*pending", text)
        if pending:
            r.error(f"strict-decisions: {len(pending)} gates remain pending")


def validate_yaml(r, strict=False):
    files = list(_iter_files(ROOT, "*.yaml")) + list(_iter_files(ROOT, "*.yml"))
    try:
        import yaml
    except ImportError:
        r.warn("PyYAML unavailable; YAML syntax skipped")
        if strict:
            r.error("strict mode requires PyYAML")
        return
    for p in files:
        # Skip template with Jinja placeholders.
        if ".template" in p.name:
            continue
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:
            r.error(f"invalid YAML {p.relative_to(ROOT)}: {e}")
    r.ok(f"YAML parsed: {len(files)}")


def validate_license_gate(r):
    if (ROOT / "LICENSE").exists():
        text = (ROOT / "docs/decisions/DECISIONS.yaml").read_text(encoding="utf-8")
        if not re.search(r"id: GATE-001[\s\S]{0,800}status: accepted", text):
            r.error("LICENSE exists while GATE-001 is not accepted")
    else:
        r.ok("license gate respected: no LICENSE before decision")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--strict-decisions", action="store_true")
    args = ap.parse_args()
    r = Report()
    validate_required(r)
    validate_json(r)
    validate_yaml(r, args.strict)
    validate_json_schemas_and_examples(r, args.strict)
    validate_adrs(r)
    validate_skills(r)
    validate_markdown_links(r)
    validate_no_control_chars(r)
    validate_decisions(r, args.strict_decisions)
    validate_license_gate(r)
    print(f"PASS {len(r.passed)}  WARN {len(r.warnings)}  ERROR {len(r.errors)}")
    for x in r.passed:
        print(f"  ✓ {x}")
    for x in r.warnings:
        print(f"  ! {x}")
    for x in r.errors:
        print(f"  ✗ {x}")
    if r.errors or (args.strict and r.warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
