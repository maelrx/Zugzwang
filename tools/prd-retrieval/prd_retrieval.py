"""Deterministic retrieval context over a colossal markdown document (ZGW-0087).

Transforms the CognitiveBoard PRD (or any structured markdown) into an auditable,
byte-reproducible retrieval context: chunking by level-2 heading with long-block
splits, BM25 (Okapi), TF-IDF (1-2 grams, sublinear tf, smooth idf, L2), reciprocal
rank fusion and accent-folded exact substring search, plus deterministic workflow
facets. Stdlib-only so a rebuild is reproducible without dependency drift.

The method families and parameters mirror the benchmark validated on this exact
document (retrieval-bench-recovered, 2026-09-06): heading chunking is the
precondition, lexical scoring over those chunks reaches R@10 ~0.98 / MRR ~0.90.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

FORMAT_VERSION = 1
MAX_CHARS_SPLIT = 1800
RRF_K = 60
CANDIDATE_DEPTH = 100
METHODS = ("rrf", "bm25", "tfidf", "exact")

HEADING_RE = re.compile(r"^(#{1,3}) (.+)$")
TOKEN_RE = re.compile(r"\w+", re.UNICODE)
SECTION_RE = re.compile(r"^(\d+)(?:\.\d+)*\.?\s")
COMBINING_MARKS_RE = re.compile(r"[\u0300-\u036f]")

# Facets by top-level section number, from the PRD's own table of contents.
PRD_SECTION_FACETS: dict[str, tuple[str, ...]] = {
    "1": ("decision",),
    "4": ("requirement",),
    "5": ("hypothesis",),
    "12": ("state-machine",),
    "13": ("budget",),
    "14": ("durability",),
    "15": ("errors",),
    "16": ("memory",),
    "35": ("test",),
    "36": ("test",),
    "37": ("test", "gate"),
    "38": ("roadmap", "work-order"),
    "41": ("adr",),
    "42": ("schema",),
    "43": ("schema",),
    "44": ("walkthrough",),
    "45": ("traceability",),
    "47": ("doc-review",),
    "48": ("handoff",),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fold(text: str) -> str:
    """NFKD-fold to ASCII lowercase without combining marks (deterministic)."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return COMBINING_MARKS_RE.sub("", decomposed)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _ngram_tokens(tokens: list[str], min_n: int, max_n: int) -> list[str]:
    out: list[str] = []
    for n in range(min_n, max_n + 1):
        if n == 1:
            out.extend(tokens)
        elif len(tokens) >= n:
            out.extend(" ".join(tokens[k : k + n]) for k in range(len(tokens) - n + 1))
    return out


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    heading: str
    parent_heading: str
    level: int
    section: str
    start_line: int
    end_line: int
    part: int
    n_parts: int
    facets: tuple[str, ...]
    text: str

    def to_record(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "heading": self.heading,
            "parent_heading": self.parent_heading,
            "level": self.level,
            "section": self.section,
            "lines": [self.start_line, self.end_line],
            "part": self.part,
            "n_parts": self.n_parts,
            "facets": list(self.facets),
            "text": self.text,
        }


def derive_facets(parent_title: str, title: str, section: str) -> tuple[str, ...]:
    """Deterministic facet extraction from heading text (accent-folded) + section."""
    t = fold(title)
    p = fold(parent_title)
    facets: set[str] = set()

    if re.search(r"adr-cb-\d+", t) or re.search(r"adr-cb-\d+", p) or "catalogo de adrs" in t:
        facets.add("adr")
    if re.search(r"cb-wo-\d+", t):
        facets.add("work-order")
    if re.search(r"\binv-\d+", t) or "invariante" in t or "invariantes" in p:
        facets.add("invariant")
    if re.search(r"\brf-\d+", t) or "requisitos" in t:
        facets.add("requirement")
    if "hipotese" in t or "hipoteses" in t:
        facets.add("hypothesis")
    if "gate" in t or "gate" in p or "definition of ready" in t or "pronto" in t:
        facets.add("gate")
    if (
        "teste" in t
        or "testes" in t
        or "cobertura" in t
        or "quality gates" in t
        or "aceitacao" in t
    ):
        facets.add("test")
    if "schema" in t or "ddl" in t or "contrato de referencia" in t or "schemas" in p:
        facets.add("schema")
    if (
        re.search(r"\bpr\b", t)
        or "pull request" in t
        or "merge" in t
        or "branch" in t
        or "work order" in t
        or "entrega" in t
        or "handoff" in t
    ):
        facets.add("workflow")
    if (
        "revisao" in t
        or "review" in t
        or "perspectivas" in t
        or "code review" in t
        or "codereview" in t
    ):
        facets.add("code-review")
    if "rastreabilidade" in t or "matriz" in t:
        facets.add("traceability")
    if "glossario" in t:
        facets.add("glossary")
    if "orcamento" in t or "custo" in t or "budget" in t:
        facets.add("budget")
    if "memoria" in t or "memory" in t:
        facets.add("memory")
    if "durabilidade" in t or "persistencia" in t or "backup" in t or "sqlite" in t:
        facets.add("durability")
    if "erro" in t or "erros" in t or "retry" in t or "repeticao" in t:
        facets.add("errors")

    facets.update(PRD_SECTION_FACETS.get(section, ()))
    return tuple(sorted(facets))


def _paragraph_spans(lines: list[str], start: int, end: int) -> list[tuple[int, int]]:
    """Split [start, end) into paragraph spans; each span includes trailing blanks."""
    spans: list[tuple[int, int]] = []
    i = start
    while i < end:
        j = i
        while j < end and lines[j].strip():
            j += 1
        while j < end and not lines[j].strip():
            j += 1
        spans.append((i, j))
        i = j
    return spans


def _pieces_with_lines(
    lines: list[str], start: int, end: int, max_chars: int
) -> list[tuple[int, int]]:
    """Accumulate paragraph spans into pieces of at most max_chars (>=1 paragraph)."""
    pieces: list[tuple[int, int]] = []
    piece_start = start
    size = 0
    for p_start, p_end in _paragraph_spans(lines, start, end):
        p_size = sum(len(lines[k]) + 1 for k in range(p_start, p_end))
        if piece_start < p_start and size + p_size > max_chars:
            pieces.append((piece_start, p_start))
            piece_start = p_start
            size = 0
        size += p_size
    if piece_start < end:
        pieces.append((piece_start, end))
    return pieces


def parse_headings(lines: list[str]) -> list[tuple[int, int, str]]:
    heads: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    return heads


def build_chunks(text: str, max_chars: int = MAX_CHARS_SPLIT) -> list[Chunk]:
    """Deterministic chunking: front matter + every level-2 heading subsection.

    Every line of the document belongs to exactly one chunk; piece boundaries
    fall on paragraph limits and preserve the original lines verbatim.
    """
    lines = text.splitlines()
    heads = parse_headings(lines)
    subs = [(i, t) for i, lv, t in heads if lv == 2]
    chunks: list[Chunk] = []
    ordinal = 0

    first_sub = subs[0][0] if subs else len(lines)
    if first_sub > 0 and any(line.strip() for line in lines[:first_sub]):
        chunks.append(
            Chunk(
                chunk_id=f"c{ordinal:04d}#0",
                heading="(preâmbulo do documento)",
                parent_heading="",
                level=0,
                section="",
                start_line=1,
                end_line=first_sub,
                part=0,
                n_parts=1,
                facets=(),
                text="\n".join(lines[:first_sub]).rstrip("\n"),
            )
        )
        ordinal += 1

    parents: list[tuple[int, str]] = [(i, t) for i, lv, t in heads if lv == 1]

    def parent_of(line_idx: int) -> str:
        best = ""
        for i, title in parents:
            if i < line_idx:
                best = title
            else:
                break
        return best

    for idx, (start, title) in enumerate(subs):
        end = subs[idx + 1][0] if idx + 1 < len(subs) else len(lines)
        parent = parent_of(start)
        sec_m = SECTION_RE.match(title)
        section = sec_m.group(1) if sec_m else ""
        facets = derive_facets(parent, title, section)
        pieces = _pieces_with_lines(lines, start, end, max_chars)
        for part, (p_start, p_end) in enumerate(pieces):
            body = "\n".join(lines[p_start:p_end])
            body = body.rstrip("\n")
            if not body.strip() and part > 0:
                continue
            n_parts = len(pieces)
            chunks.append(
                Chunk(
                    chunk_id=f"c{ordinal:04d}#{part}",
                    heading=title,
                    parent_heading=parent,
                    level=2,
                    section=section,
                    start_line=p_start + 1,
                    end_line=p_end,
                    part=part,
                    n_parts=n_parts,
                    facets=facets,
                    text=f"{title}\n{body}",
                )
            )
        ordinal += 1

    covered: list[tuple[int, int]] = []
    for c in chunks:
        span = (c.start_line - 1, c.end_line)
        if covered and span[0] < covered[-1][1]:
            raise ValueError(f"overlapping chunks at line {span[0] + 1}")
        covered.append(span)
    return chunks


@dataclass(frozen=True)
class _Index:
    bm25_idf: dict[str, float]
    bm25_postings: dict[str, list[tuple[int, int]]]
    bm25_doc_len: list[int]
    bm25_avgdl: float
    tfidf_postings: dict[str, list[tuple[int, float]]]
    folded_texts: list[str]


def _build_index(chunks: list[Chunk], min_ngram: int = 1, max_ngram: int = 2) -> _Index:
    n_docs = len(chunks)
    token_lists = [tokenize(c.text) for c in chunks]

    doc_len = [len(toks) for toks in token_lists]
    avgdl = sum(doc_len) / n_docs if n_docs else 0.0

    df: dict[str, int] = {}
    for toks in token_lists:
        for term in set(toks):
            df[term] = df.get(term, 0) + 1

    raw_idf = {
        term: math.log(n_docs - freq + 0.5) - math.log(freq + 0.5) for term, freq in df.items()
    }
    eps_floor = 0.25 * (sum(raw_idf.values()) / len(raw_idf) if raw_idf else 0.0)
    bm25_idf = {term: (v if v >= 0 else eps_floor) for term, v in raw_idf.items()}

    bm25_postings: dict[str, list[tuple[int, int]]] = {}
    for doc_id, toks in enumerate(token_lists):
        counts: dict[str, int] = {}
        for tok in toks:
            counts[tok] = counts.get(tok, 0) + 1
        for term in sorted(counts):
            bm25_postings.setdefault(term, []).append((doc_id, counts[term]))

    tf_counts: list[dict[str, int]] = []
    for toks in token_lists:
        grams = _ngram_tokens(toks, min_ngram, max_ngram)
        counts: dict[str, int] = {}
        for g in grams:
            counts[g] = counts.get(g, 0) + 1
        tf_counts.append(counts)

    tfidf_df: dict[str, int] = {}
    for counts in tf_counts:
        for term in counts:
            tfidf_df[term] = tfidf_df.get(term, 0) + 1

    idf = {term: math.log((1 + n_docs) / (1 + freq)) + 1.0 for term, freq in tfidf_df.items()}

    doc_weights: list[dict[str, float]] = []
    for counts in tf_counts:
        weights = {term: (1.0 + math.log(tf)) * idf[term] for term, tf in counts.items()}
        norm = math.sqrt(sum(w * w for w in weights.values()))
        if norm > 0:
            weights = {term: w / norm for term, w in weights.items()}
        doc_weights.append(weights)

    tfidf_postings: dict[str, list[tuple[int, float]]] = {}
    for doc_id, weights in enumerate(doc_weights):
        for term in sorted(weights):
            tfidf_postings.setdefault(term, []).append((doc_id, weights[term]))

    folded = [fold(c.text) for c in chunks]
    return _Index(bm25_idf, bm25_postings, doc_len, avgdl, tfidf_postings, folded)


class RetrievalContext:
    """In-memory deterministic retrieval over built chunks."""

    def __init__(self, chunks: list[Chunk], max_ngram: int = 2):
        self.chunks = chunks
        self.max_ngram = max_ngram
        self._index = _build_index(chunks, 1, max_ngram)

    def _rank_bm25(
        self, query_tokens: list[str], top: int, allowed: set[int] | None = None
    ) -> list[tuple[int, float]]:
        idx = self._index
        scores = [0.0] * len(self.chunks)
        k1, b = 1.5, 0.75
        for term in query_tokens:
            postings = idx.bm25_postings.get(term)
            if not postings:
                continue
            weight = idx.bm25_idf[term]
            for doc_id, tf in postings:
                if allowed is not None and doc_id not in allowed:
                    continue
                denom = tf + k1 * (1.0 - b + b * idx.bm25_doc_len[doc_id] / idx.bm25_avgdl)
                scores[doc_id] += weight * tf * (k1 + 1.0) / denom
        return self._rank_scores(scores, top, allowed)

    def _rank_tfidf(
        self, query_tokens: list[str], top: int, allowed: set[int] | None = None
    ) -> list[tuple[int, float]]:
        q_counts: dict[str, int] = {}
        for gram in _ngram_tokens(query_tokens, 1, self.max_ngram):
            q_counts[gram] = q_counts.get(gram, 0) + 1
        q_weights = {
            term: (1.0 + math.log(tf)) * self._query_idf(term) for term, tf in q_counts.items()
        }
        norm = math.sqrt(sum(w * w for w in q_weights.values()))
        if norm > 0:
            q_weights = {term: w / norm for term, w in q_weights.items()}

        acc: dict[int, float] = {}
        for term, q_w in sorted(q_weights.items()):
            for doc_id, d_w in self._index.tfidf_postings.get(term, ()):
                if allowed is not None and doc_id not in allowed:
                    continue
                acc[doc_id] = acc.get(doc_id, 0.0) + q_w * d_w
        ranked = sorted(acc.items(), key=lambda kv: (-kv[1], self.chunks[kv[0]].chunk_id))
        return ranked[:top]

    def _query_idf(self, term: str) -> float:
        n_docs = len(self.chunks)
        df = len(self._index.tfidf_postings.get(term, ()))
        return math.log((1 + n_docs) / (1 + df)) + 1.0

    def _rank_exact(
        self, query: str, top: int, allowed: set[int] | None = None
    ) -> list[tuple[int, float]]:
        needle = fold(query)
        if not needle:
            return []
        hits = [
            (i, 1.0)
            for i, folded in enumerate(self._index.folded_texts)
            if (allowed is None or i in allowed) and needle in folded
        ]
        hits.sort(key=lambda iv: (len(self.chunks[iv[0]].text), self.chunks[iv[0]].chunk_id))
        return hits[:top]

    def _rank_scores(
        self, scores: list[float], top: int, allowed: set[int] | None = None
    ) -> list[tuple[int, float]]:
        ranked = [
            (i, s) for i, s in enumerate(scores) if s > 0.0 and (allowed is None or i in allowed)
        ]
        ranked.sort(key=lambda iv: (-iv[1], self.chunks[iv[0]].chunk_id))
        return ranked[:top]

    def search(
        self,
        query: str,
        method: str = "rrf",
        top: int = 10,
        allowed: set[int] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Deterministic ranked search; ties break by (score desc, chunk_id asc).

        `allowed` restricts the candidate document ids (facet/section filters)
        without changing the scoring formulas.
        """
        if method not in METHODS:
            raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")
        query = query.strip()
        if not query:
            return []
        if method == "exact":
            hits = self._rank_exact(query, top, allowed)
        else:
            query_tokens = tokenize(query)
            if not query_tokens:
                return []
            depth = max(top, CANDIDATE_DEPTH)
            if method == "bm25":
                hits = self._rank_bm25(query_tokens, depth, allowed)
            elif method == "tfidf":
                hits = self._rank_tfidf(query_tokens, depth, allowed)
            else:
                fused: dict[int, float] = {}
                for ranking in (
                    self._rank_bm25(query_tokens, depth, allowed),
                    self._rank_tfidf(query_tokens, depth, allowed),
                ):
                    for rank, (doc_id, _) in enumerate(ranking, 1):
                        fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
                ordered = sorted(
                    fused.items(), key=lambda kv: (-kv[1], self.chunks[kv[0]].chunk_id)
                )
                hits = ordered[:depth]
        return [(self.chunks[i], score) for i, score in hits[:top]]


def context_manifest(source_path: Path, source_text: str, chunks: list[Chunk]) -> dict[str, object]:
    lines = source_text.splitlines()
    return {
        "format_version": FORMAT_VERSION,
        "source": {
            "name": source_path.name,
            "sha256": sha256_bytes(source_text.encode("utf-8")),
            "bytes": len(source_text.encode("utf-8")),
            "lines": len(lines),
        },
        "config": {
            "chunking": "heading-level2 + paragraph split",
            "max_chars_split": MAX_CHARS_SPLIT,
            "bm25": {"k1": 1.5, "b": 0.75, "epsilon_floor": 0.25},
            "tfidf": {
                "ngram_range": [1, 2],
                "sublinear_tf": True,
                "smooth_idf": True,
                "norm": "l2",
            },
            "rrf": {"k": RRF_K, "candidate_depth": CANDIDATE_DEPTH},
            "tokenizer": r"\w+ UNICODE on lowercase (NFKC-unspecified, str.lower)",
        },
        "counts": {
            "chunks": len(chunks),
            "subsections": sum(1 for c in chunks if c.level == 2 and c.part == 0),
            "level2_pieces": sum(1 for c in chunks if c.level == 2),
            "facets": sorted({f for c in chunks for f in c.facets}),
        },
    }


def render_context(source_path: Path, source_text: str, chunks: list[Chunk]) -> dict[str, bytes]:
    """Render derived artifacts in memory (no timestamps, sorted keys)."""
    chunks_bytes = (
        "\n".join(
            json.dumps(c.to_record(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for c in chunks
        )
        + "\n"
    ).encode("utf-8")

    facet_map: dict[str, list[str]] = {}
    for c in chunks:
        for facet in c.facets:
            facet_map.setdefault(facet, []).append(c.chunk_id)
    facets_bytes = json.dumps(
        {k: sorted(v) for k, v in sorted(facet_map.items())},
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")

    manifest = context_manifest(source_path, source_text, chunks)
    manifest["artifacts"] = {
        "chunks.jsonl": sha256_bytes(chunks_bytes),
        "facets.json": sha256_bytes(facets_bytes),
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode(
        "utf-8"
    )

    return {
        "chunks.jsonl": chunks_bytes,
        "facets.json": facets_bytes,
        "MANIFEST.json": manifest_bytes,
    }


def write_context(
    out_dir: Path, source_path: Path, source_text: str, chunks: list[Chunk]
) -> dict[str, str]:
    """Write derived artifacts deterministically (no timestamps); returns digests."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = render_context(source_path, source_text, chunks)
    for name, payload in rendered.items():
        (out_dir / name).write_bytes(payload)
    return {name: sha256_bytes(payload) for name, payload in rendered.items()}


def rendered_names() -> tuple[str, ...]:
    return ("chunks.jsonl", "facets.json", "MANIFEST.json")


def load_chunks(context_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for line in (context_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        chunks.append(
            Chunk(
                chunk_id=r["chunk_id"],
                heading=r["heading"],
                parent_heading=r["parent_heading"],
                level=r["level"],
                section=r["section"],
                start_line=r["lines"][0],
                end_line=r["lines"][1],
                part=r["part"],
                n_parts=r["n_parts"],
                facets=tuple(r["facets"]),
                text=r["text"],
            )
        )
    return chunks


def read_manifest(context_dir: Path) -> dict[str, object]:
    return json.loads((context_dir / "MANIFEST.json").read_text(encoding="utf-8"))
