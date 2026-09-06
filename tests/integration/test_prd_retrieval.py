"""Offline tests for the deterministic PRD retrieval context (ZGW-0087).

Default suite: synthetic fixture only. The real-PRD acceptance suite (same
50-question ground truth validated in the retrieval benchmark) runs whenever
the untracked PRD is present at the repo root; it skips otherwise.
"""

import importlib.util
import json
import sys
from itertools import pairwise
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_DIR = REPO_ROOT / "tools" / "prd-retrieval"
FIXTURE = REPO_ROOT / "fixtures" / "retrieval" / "mini_prd.md"
NATURAL_JSON = REPO_ROOT / "fixtures" / "retrieval" / "natural_questions.json"
PRD = REPO_ROOT / "Zugzwang_PRD_CognitiveBoard_v0.1.md"

sys.path.insert(0, str(TOOL_DIR))

import prd_retrieval  # noqa: E402

pytestmark = pytest.mark.integration


def _load_cli(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOL_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def fixture_chunks(fixture_text: str) -> list[prd_retrieval.Chunk]:
    return prd_retrieval.build_chunks(fixture_text)


@pytest.fixture(scope="module")
def fixture_ctx(fixture_chunks: list[prd_retrieval.Chunk]) -> prd_retrieval.RetrievalContext:
    return prd_retrieval.RetrievalContext(fixture_chunks)


def _heading_map(chunks: list[prd_retrieval.Chunk]) -> dict[str, prd_retrieval.Chunk]:
    return {c.heading: c for c in chunks if c.level == 2 and c.part == 0}


def _chunk_spans(chunks: list[prd_retrieval.Chunk]) -> list[tuple[int, int]]:
    return [(c.start_line - 1, c.end_line) for c in chunks]


def test_chunking_is_deterministic(
    fixture_text: str, fixture_chunks: list[prd_retrieval.Chunk]
) -> None:
    again = prd_retrieval.build_chunks(fixture_text)
    assert [c.to_record() for c in again] == [c.to_record() for c in fixture_chunks]

    rendered_a = prd_retrieval.render_context(FIXTURE, fixture_text, fixture_chunks)
    rendered_b = prd_retrieval.render_context(FIXTURE, fixture_text, again)
    assert rendered_a == rendered_b


def test_write_is_byte_identical_across_dirs(
    fixture_text: str, fixture_chunks: list[prd_retrieval.Chunk], tmp_path: Path
) -> None:
    digests_a = prd_retrieval.write_context(tmp_path / "a", FIXTURE, fixture_text, fixture_chunks)
    digests_b = prd_retrieval.write_context(tmp_path / "b", FIXTURE, fixture_text, fixture_chunks)
    assert digests_a == digests_b


def test_every_line_covered_exactly_once(
    fixture_text: str, fixture_chunks: list[prd_retrieval.Chunk]
) -> None:
    n_lines = len(fixture_text.splitlines())
    spans = _chunk_spans(fixture_chunks)
    assert spans[0][0] == 0
    assert spans[-1][1] == n_lines
    for (_, a_end), (b_start, _) in pairwise(spans):
        assert a_end == b_start, f"gap/overlap between {a_end} and {b_start}"
    for start, end in spans:
        assert start < end


def test_long_subsection_is_split_with_contiguous_parts(
    fixture_chunks: list[prd_retrieval.Chunk],
) -> None:
    long_heading = "38.11. Bloco longo para split determinístico"
    parts = sorted((c for c in fixture_chunks if c.heading == long_heading), key=lambda c: c.part)
    assert len(parts) >= 2
    assert [c.part for c in parts] == list(range(len(parts)))
    assert all(c.n_parts == len(parts) for c in parts)
    for prev, nxt in pairwise(parts):
        assert prev.end_line + 1 == nxt.start_line
    assert parts[0].start_line < parts[0].end_line


def test_facets_extracted_deterministically(fixture_chunks: list[prd_retrieval.Chunk]) -> None:
    heads = _heading_map(fixture_chunks)
    assert heads["38.7. Definição de pronto de uma PR"].facets == (
        "gate",
        "roadmap",
        "work-order",
        "workflow",
    )
    assert heads["35.2. Metas de cobertura de testes"].facets == ("test",)
    assert heads["17.2. Gates de decisão humana"].facets == ("gate",)
    assert heads["17.6. Quando considerar BM25 e embeddings"].facets == ()
    assert "adr" in heads["ADR-CB-013. Retrieval elegível antes de ranking"].facets
    assert {"work-order", "roadmap"}.issubset(heads["38.10. CB-WO-09: memória condicionada"].facets)
    assert "code-review" in heads["38.2. Revisão por perspectivas"].facets


def test_search_is_relevant_and_deterministic(fixture_ctx: prd_retrieval.RetrievalContext) -> None:
    first = fixture_ctx.search("gate pendente não é recomendação aceita", method="rrf", top=3)
    second = fixture_ctx.search("gate pendente não é recomendação aceita", method="rrf", top=3)
    assert [c.chunk_id for c, _ in first] == [c.chunk_id for c, _ in second]
    assert first[0][0].heading == "17.2. Gates de decisão humana"


def test_exact_mode_is_accent_insensitive(fixture_ctx: prd_retrieval.RetrievalContext) -> None:
    hits = fixture_ctx.search("memoria condicionada", method="exact", top=10)
    assert hits, "substring exata sem acento deve encontrar 'memória condicionada'"
    assert any("CB-WO-09" in c.heading for c, _ in hits)


def test_empty_and_unknown_queries(fixture_ctx: prd_retrieval.RetrievalContext) -> None:
    assert fixture_ctx.search("", method="rrf", top=5) == []
    assert fixture_ctx.search("   ", method="bm25", top=5) == []
    assert fixture_ctx.search("zzzqqqxyzzy inexistente", method="rrf", top=5) == []
    with pytest.raises(ValueError):
        fixture_ctx.search("qualquer coisa", method="vector", top=5)


def test_facet_filter_restricts_candidates(fixture_ctx: prd_retrieval.RetrievalContext) -> None:
    allowed = {i for i, c in enumerate(fixture_ctx.chunks) if "work-order" in c.facets}
    hits = fixture_ctx.search("memória condicionada", method="rrf", top=10, allowed=allowed)
    assert hits
    assert all("work-order" in c.facets for c, _ in hits)


def test_write_load_roundtrip(
    fixture_text: str, fixture_chunks: list[prd_retrieval.Chunk], tmp_path: Path
) -> None:
    prd_retrieval.write_context(tmp_path / "ctx", FIXTURE, fixture_text, fixture_chunks)
    loaded = prd_retrieval.load_chunks(tmp_path / "ctx")
    assert [c.to_record() for c in loaded] == [c.to_record() for c in fixture_chunks]
    manifest = prd_retrieval.read_manifest(tmp_path / "ctx")
    assert manifest["source"]["sha256"] == prd_retrieval.sha256_bytes(fixture_text.encode("utf-8"))
    assert manifest["counts"]["subsections"] == 10
    assert manifest["counts"]["facets"] == sorted({f for c in fixture_chunks for f in c.facets})


def test_build_cli_and_check_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    build = _load_cli("build_context")
    out = tmp_path / "ctx"
    assert build.main(["--doc", str(FIXTURE), "--out", str(out)]) == 0
    assert build.main(["--doc", str(FIXTURE), "--out", str(out), "--check"]) == 0
    (out / "facets.json").write_bytes(b"corrompido\n")
    assert build.main(["--doc", str(FIXTURE), "--out", str(out), "--check"]) == 2
    assert build.main(["--doc", str(tmp_path / "ausente.md"), "--out", str(out)]) == 1
    _ = capsys.readouterr()


def test_query_cli_json_and_stale_rebuild(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    query = _load_cli("query_context")
    ctx_dir = tmp_path / "ctx"
    argv = [
        "gate pendente não é recomendação aceita",
        "--doc",
        str(FIXTURE),
        "--context-dir",
        str(ctx_dir),
        "--json",
        "--top-k",
        "3",
    ]
    assert query.main(argv) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["rebuilt"] is True
    assert first["results"][0]["heading"] == "17.2. Gates de decisão humana"
    assert first["results"][0]["rank"] == 1

    assert query.main(argv) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["rebuilt"] is False
    assert [r["chunk_id"] for r in second["results"]] == [r["chunk_id"] for r in first["results"]]

    stale_argv = [*argv, "--no-rebuild"]
    pristine_manifest = (ctx_dir / "MANIFEST.json").read_bytes()
    (ctx_dir / "MANIFEST.json").write_text('{"source": {"sha256": "stale"}}', encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        query.main(stale_argv)
    assert exc.value.code == 1

    # tampered artifact with intact manifest is also stale (digest verification)
    (ctx_dir / "MANIFEST.json").write_bytes(pristine_manifest)
    (ctx_dir / "facets.json").write_bytes(b"corrompido\n")
    assert query.main(argv) == 0
    third = json.loads(capsys.readouterr().out)
    assert third["rebuilt"] is True
    _ = capsys.readouterr()


def test_query_cli_filters(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    query = _load_cli("query_context")
    argv = [
        "memória condicionada",
        "--doc",
        str(FIXTURE),
        "--context-dir",
        str(tmp_path / "ctx"),
        "--json",
        "--top-k",
        "20",
        "--facet",
        "work-order",
        "--section",
        "38",
        "--heading-substr",
        "CB-WO-09",
    ]
    assert query.main(argv) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["results"]
    for result in payload["results"]:
        assert "work-order" in result["facets"]
        assert result["section"] == "38"
        assert "CB-WO-09" in result["heading"]


def _subsection_rank(chunks: list[prd_retrieval.Chunk], ranked: list, gt_heading: str):
    for pos, (chunk, _) in enumerate(ranked, 1):
        if chunk.level == 2 and chunk.heading == gt_heading:
            return pos
    return None


def _metrics(ranks: list[int | None]) -> dict[str, float]:
    n = len(ranks)
    return {
        "r1": sum(1 for r in ranks if r == 1) / n,
        "r10": sum(1 for r in ranks if r is not None and r <= 10) / n,
        "mrr": sum(1.0 / r if r else 0.0 for r in ranks) / n,
    }


PRD_SKIP = pytest.mark.skipif(not PRD.exists(), reason="PRD do CognitiveBoard não presente na raiz")


@PRD_SKIP
def test_prd_real_determinism_and_coverage() -> None:
    source_text = PRD.read_text(encoding="utf-8")
    chunks = prd_retrieval.build_chunks(source_text)

    spans = _chunk_spans(chunks)
    assert spans[-1][1] == len(source_text.splitlines())
    for (_, a_end), (b_start, _) in pairwise(spans):
        assert a_end == b_start

    subsections = [c for c in chunks if c.level == 2 and c.part == 0]
    assert len(subsections) == 291

    rendered = prd_retrieval.render_context(PRD, source_text, chunks)
    with_pristine = prd_retrieval.build_chunks(PRD.read_text(encoding="utf-8"))
    rendered_again = prd_retrieval.render_context(PRD, source_text, with_pristine)
    assert rendered == rendered_again


@PRD_SKIP
def test_prd_real_natural_questions_acceptance() -> None:
    questions = json.loads(NATURAL_JSON.read_text(encoding="utf-8"))["questions"]
    assert len(questions) == 50

    chunks = prd_retrieval.build_chunks(PRD.read_text(encoding="utf-8"))
    ctx = prd_retrieval.RetrievalContext(chunks)

    for method, floor_mrr in (("rrf", 0.86), ("bm25", 0.85), ("tfidf", 0.85)):
        ranks = []
        for item in questions:
            ranked = ctx.search(item["q"], method=method, top=100)
            ranks.append(_subsection_rank(chunks, ranked, item["gt_heading"]))
        m = _metrics(ranks)
        assert m["r10"] >= 0.94, f"{method}: R@10 {m['r10']:.3f} abaixo do bar"
        assert m["mrr"] >= floor_mrr, f"{method}: MRR {m['mrr']:.3f} abaixo do bar"
        if method == "rrf":
            assert m["r1"] >= 0.82, f"rrf: R@1 {m['r1']:.3f} abaixo do bar"

    cov_ranks = [
        _subsection_rank(chunks, ctx.search(c.heading, method="tfidf", top=100), c.heading)
        for c in chunks
        if c.level == 2 and c.part == 0
    ]
    assert len(cov_ranks) == 291
    cov = _metrics(cov_ranks)
    assert cov["r1"] == 1.0
    assert cov["r10"] == 1.0


def test_blank_preamble_and_no_subsections_are_covered() -> None:
    blank_preamble = "\n\n\n# Título\n\n## 1.1. Seção\n\ntexto\n"
    chunks = prd_retrieval.build_chunks(blank_preamble)
    spans = _chunk_spans(chunks)
    assert spans[0][0] == 0
    assert spans[-1][1] == len(blank_preamble.splitlines())
    for (_, a_end), (b_start, _) in pairwise(spans):
        assert a_end == b_start

    no_subs = "# Só título\n\ntexto solto sem subseções\n"
    chunks2 = prd_retrieval.build_chunks(no_subs)
    assert len(chunks2) == 1
    assert chunks2[0].start_line == 1
    assert chunks2[0].end_line == len(no_subs.splitlines())
    ctx2 = prd_retrieval.RetrievalContext(chunks2)
    assert ctx2.search("texto solto", method="rrf", top=3)
