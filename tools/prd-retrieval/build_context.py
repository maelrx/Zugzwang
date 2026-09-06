#!/usr/bin/env python3
"""Build (or verify) the deterministic retrieval context for the CognitiveBoard PRD.

The derived artifacts are byte-identical across rebuilds: no timestamps, sorted
keys, fixed separators. `--check` rebuilds in memory and compares every artifact
byte-for-byte against the on-disk context.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import prd_retrieval

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOC = REPO_ROOT / "Zugzwang_PRD_CognitiveBoard_v0.1.md"
DEFAULT_OUT = Path(__file__).resolve().parent / "context"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC, help="markdown source document")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="context output directory")
    parser.add_argument(
        "--check",
        action="store_true",
        help="rebuild in memory and verify artifacts byte-for-byte (no writes)",
    )
    args = parser.parse_args(argv)

    if not args.doc.exists():
        return prd_retrieval.fail(
            "E-SOURCE-MISSING",
            "documento-fonte inexistente",
            f"--doc {args.doc}",
            "corrigir --doc e refazer",
            f"Path.exists() em {args.doc}",
        )
    source_text = args.doc.read_text(encoding="utf-8")
    chunks = prd_retrieval.build_chunks(source_text)

    if args.check:
        if not all((args.out / name).exists() for name in prd_retrieval.rendered_names()):
            return prd_retrieval.fail(
                "E-CONTEXT-MISSING",
                "contexto inexistente",
                f"--out {args.out}",
                "rodar build_context.py (sem --check) e repetir",
                f"{args.out}/MANIFEST.json",
            )
        rendered = prd_retrieval.render_context(args.doc, source_text, chunks)
        ok = True
        for name, payload in rendered.items():
            on_disk = (args.out / name).read_bytes()
            same = on_disk == payload
            ok = ok and same
            status = "ok" if same else "DIFERE"
            print(f"  {name}: {prd_retrieval.sha256_bytes(on_disk)[:16]}… {status}")
        if not ok:
            print("verificação: FAIL (contexto stale — rebuild determinístico)")
            return prd_retrieval.fail(
                "E-CONTEXT-STALE",
                "artefatos diferem do rebuild determinístico",
                f"--out {args.out}",
                "rebuild determinístico seguro (mesma fonte/config)",
                f"{args.out}/MANIFEST.json",
                code=2,
            )
        print("verificação: PASS")
        return 0

    digests = prd_retrieval.write_context(args.out, args.doc, source_text, chunks)
    manifest = prd_retrieval.read_manifest(args.out)
    counts = manifest["counts"]
    source = manifest["source"]
    print(f"fonte: {source['name']} sha256={source['sha256'][:16]}… ({source['lines']} linhas)")
    print(f"chunks: {counts['chunks']} (subseções: {counts['subsections']})")
    print(f"facets: {', '.join(counts['facets'])}")
    print(f"contexto em: {args.out}")
    for name, digest in digests.items():
        print(f"  {name}: {digest[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
