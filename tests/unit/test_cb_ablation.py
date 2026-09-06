"""CB-WO-11 acceptance — ablation analysis offline (PRD §38.12, TEST-071..074).

Unit-marked, deterministic, fixtures only:

- TEST-071 métrica de avaliação: perspectiva correta; mate fora da média de CP;
- TEST-072 referência ruidosa: diferença negativa preservada e sinalizada;
- TEST-073 pareamento científico: mesmas posições/splits/versões/rota;
- TEST-074 budget comparativo: trabalho formal pré-computado entra no custo.
"""

import importlib.util

import pytest


def _analysis():
    from pathlib import Path as _Path

    script = _Path(__file__).resolve().parents[2] / "scripts" / "analyze_cb_ablation.py"
    spec = importlib.util.spec_from_file_location("analyze_cb_ablation", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _analysis()
analyze, mean_cp, pair_key, parse_score, signed_delta = (
    _MOD.analyze,
    _MOD.mean_cp,
    _MOD.pair_key,
    _MOD.parse_score,
    _MOD.signed_delta,
)

pytestmark = pytest.mark.unit


def test_eval_metric_perspective_and_mate_excluded() -> None:
    """TEST-071: perspectiva correta; mate fora da média de CP."""
    white = parse_score(42, "white")
    assert white == {"cp": 42.0, "mate": None, "perspective": "white"}
    mate = parse_score("#3", "white")
    assert mate["cp"] is None
    assert mate["mate"] == "#3"
    assert mean_cp([white, mate]) == 42.0
    assert mean_cp([mate]) is None


def test_noisy_reference_keeps_sign() -> None:
    """TEST-072: diferença negativa preservada e sinalizada."""
    assert signed_delta(10.0, 7.0) == {"delta": -3.0, "sign": "-"}
    assert signed_delta(7.0, 10.0) == {"delta": 3.0, "sign": "+"}
    assert signed_delta(5.0, 5.0) == {"delta": 0.0, "sign": "0"}


def test_scientific_pairing() -> None:
    """TEST-073: condições usam mesmas posições, splits e versões."""
    base = {
        "position": "startpos",
        "split": "development",
        "versions": "perception/v0.1",
        "route": "fake-direct",
        "seed": "7",
    }
    assert pair_key(base) is not None
    other = dict(base, route="other-route")
    assert pair_key(other) != pair_key(base)
    assert pair_key({"position": "x"}) is None


def test_comparative_budget_counts_formal_work() -> None:
    """TEST-074: trabalho formal pré-computado entra no custo."""
    pairs = [
        (
            {
                "position": "p1",
                "split": "development",
                "versions": "v",
                "route": "fake-direct",
                "seed": "1",
                "selection": "e2e4",
                "ops_charged": 2,
            },
            {
                "position": "p1",
                "split": "development",
                "versions": "v",
                "route": "fake-direct",
                "seed": "1",
                "selection": "e2e4",
                "ops_charged": 3,
            },
        ),
        (
            {
                "position": "p2",
                "split": "development",
                "versions": "v",
                "route": "fake-direct",
                "seed": "2",
                "selection": "e2e4",
                "ops_charged": 1,
            },
            {
                "position": "p2",
                "split": "other",
                "versions": "v",
                "route": "fake-direct",
                "seed": "2",
                "selection": "d2d4",
                "ops_charged": 9,
            },
        ),
    ]
    report = analyze(pairs)
    assert report["pairs_complete"] == 1
    assert report["pairs_excluded"] == 1
    assert report["match_rate"] == 1.0
    assert report["ops_deltas"] == [{"delta": 1.0, "sign": "+"}]
    assert report["cost_money"] == "unknown"
    assert report["cost_formal_ops"] == 1.0
