#!/usr/bin/env python3
"""Query the deterministic retrieval context of the CognitiveBoard PRD.

If the context directory is missing or the source document changed (sha256
mismatch), the context is rebuilt automatically (deterministically) unless
--no-rebuild is given, so a long session never silently serves a stale index.

Examples:
  query_context.py "Quais tools o CognitiveBoard expõe?"
  query_context.py "ADR-CB-007" --method exact --full
  query_context.py "definition of done" --facet workflow --facet code-review
  query_context.py "gates" --section 37 --top-k 5 --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import prd_retrieval

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOC = REPO_ROOT / "Zugzwang_PRD_CognitiveBoard_v0.1.md"
DEFAULT_CONTEXT = Path(__file__).resolve().parent / "context"


def ensure_context(
    doc_path: Path, context_dir: Path, rebuild: bool
) -> tuple[list[prd_retrieval.Chunk], str, bool]:
    """Load chunks from disk; rebuild automatically when missing or stale."""
    doc_sha = prd_retrieval.sha256_bytes(doc_path.read_bytes())
    manifest_path = context_dir / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = manifest.get("source", {})
        same_format = manifest.get("format_version") == prd_retrieval.FORMAT_VERSION
        if (
            same_format
            and source.get("sha256") == doc_sha
            and (context_dir / "chunks.jsonl").exists()
        ):
            return prd_retrieval.load_chunks(context_dir), doc_sha, False
        if not rebuild:
            print(
                "erro: contexto stale/ausente e --no-rebuild ativo — rode build_context.py",
                file=sys.stderr,
            )
            raise SystemExit(1)
        reason = "formato" if not same_format else f"sha256 {source.get('sha256', '?')[:12]}…"
        print(f"aviso: contexto stale ({reason}) — rebuild determinístico", file=sys.stderr)
    else:
        if not rebuild:
            print(
                f"erro: contexto inexistente em {context_dir} e --no-rebuild ativo", file=sys.stderr
            )
            raise SystemExit(1)
        print(f"aviso: contexto inexistente em {context_dir} — build", file=sys.stderr)
    source_text = doc_path.read_text(encoding="utf-8")
    chunks = prd_retrieval.build_chunks(source_text)
    prd_retrieval.write_context(context_dir, doc_path, source_text, chunks)
    return chunks, doc_sha, True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("query", nargs="+", help="consulta em linguagem natural ou literal")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC, help="documento-fonte")
    parser.add_argument(
        "--context-dir", type=Path, default=DEFAULT_CONTEXT, help="diretório do contexto"
    )
    parser.add_argument("--method", choices=prd_retrieval.METHODS, default="rrf")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--facet", action="append", default=[], help="filtra candidatos por facet (repetível)"
    )
    parser.add_argument("--section", default=None, help="filtra por seção top-level (ex.: 42)")
    parser.add_argument(
        "--heading-substr", default=None, help="filtra por substring do heading (accent-folded)"
    )
    parser.add_argument("--full", action="store_true", help="imprime o texto integral dos chunks")
    parser.add_argument("--json", action="store_true", help="saída JSON estruturada")
    parser.add_argument("--no-rebuild", action="store_true", help="nunca escreve; falha se stale")
    args = parser.parse_args(argv)

    if not args.doc.exists():
        print(f"erro: documento-fonte não encontrado: {args.doc}", file=sys.stderr)
        return 1

    chunks, doc_sha, rebuilt = ensure_context(args.doc, args.context_dir, not args.no_rebuild)
    query = " ".join(args.query)

    allowed: set[int] | None = None
    if args.facet or args.section or args.heading_substr:
        wanted_facets = set(args.facet)
        heading_needle = prd_retrieval.fold(args.heading_substr) if args.heading_substr else None
        allowed = set()
        for i, chunk in enumerate(chunks):
            if wanted_facets and not wanted_facets.issubset(set(chunk.facets)):
                continue
            if args.section and chunk.section != args.section:
                continue
            if heading_needle and heading_needle not in prd_retrieval.fold(chunk.heading):
                continue
            allowed.add(i)
        if not allowed:
            print("nenhum chunk passa nos filtros (facet/seção/heading)", file=sys.stderr)
            return 1

    ctx = prd_retrieval.RetrievalContext(chunks)
    t0 = time.perf_counter()
    hits = ctx.search(query, method=args.method, top=args.top_k, allowed=allowed)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    if args.json:
        payload = {
            "query": query,
            "method": args.method,
            "source_sha256": doc_sha,
            "rebuilt": rebuilt,
            "latency_ms": round(elapsed_ms, 2),
            "results": [
                {
                    "rank": rank,
                    "chunk_id": chunk.chunk_id,
                    "heading": chunk.heading,
                    "parent_heading": chunk.parent_heading,
                    "section": chunk.section,
                    "lines": [chunk.start_line, chunk.end_line],
                    "facets": list(chunk.facets),
                    "score": round(score, 6),
                    "text": chunk.text,
                }
                for rank, (chunk, score) in enumerate(hits, 1)
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(
        f"# {len(hits)} resultado(s) · método={args.method} · k={args.top_k} · "
        f"{elapsed_ms:.1f} ms · fonte {doc_sha[:12]}…"
        + (" (rebuild automático)" if rebuilt else "")
    )
    for rank, (chunk, score) in enumerate(hits, 1):
        title = f"§{chunk.section} " if chunk.section else ""
        print(f"\n{rank}. {chunk.chunk_id}  score={score:.4f}  {title}{chunk.heading}")
        print(
            f"   {args.doc.name}:{chunk.start_line}-{chunk.end_line}  facets={','.join(chunk.facets) or '-'}"
        )
        if args.full:
            print(chunk.text)
        else:
            excerpt = chunk.text.replace("\n", " ")
            print(f"   {excerpt[:200]}{'…' if len(excerpt) > 200 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
