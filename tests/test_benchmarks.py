"""Benchmarks: v1 (the checkpoint yardstick) and v2 (gap-aware) never mix; checkpoints unchanged."""
from helpers import FakeDB

from backtest import rule_report as rr


def _db():
    db = FakeDB()
    db.add(rr.BENCH_EVENT, {"rule_id": "a", "version": 1, "trades": 100, "mean": 50.0, "std": 900.0, "net": 5000})
    db.add(rr.BENCH_EVENT, {"rule_id": "a", "version": 2, "trades": 100, "mean": 20.0, "std": 900.0, "net": 2000})
    return db


def test_versions_kept_apart():
    db = _db()
    assert rr.BENCH_VERSION == 1 and rr.BENCH_VERSION_V2 == 2
    assert rr.stored_benchmarks(db)["a"]["mean"] == 50.0                  # default = v1, as before
    assert rr.stored_benchmarks(db, rr.BENCH_VERSION_V2)["a"]["mean"] == 20.0
    assert rr.stored_benchmarks(db, 3) == {}


def test_checkpoint_rules_unchanged():
    bench = {"trades": 100, "mean": 50.0, "std": 900.0}
    assert rr.checkpoint_status([], None) == "benchmark not available yet"
    assert rr.checkpoint_status([10.0] * 5, bench).startswith("collecting data (5/10")
    assert "PASS" in rr.checkpoint_status([300.0] * 20 + [-200.0] * 10, bench)
    assert "FAIL" in rr.checkpoint_status([100.0] * 10 + [-200.0] * 20, bench)
    assert rr.BENCHMARK_END.isoformat() == "2026-09-26" and rr.PF_PASS == 1.15


def test_v3_version_and_comparison_text():
    from backtest import run_benchmark_v2 as rb
    assert rr.BENCH_VERSION_V3 == 3
    v = {"volatility_expansion_rule_v2_nifty50": {"trades": 10, "net": 5.0, "pf": 1.0, "mean": 0.5}}
    t = rb.comparison_text(v, v, v)
    assert "v3:" in t and "v1 remains the yardstick" in t
    assert "v3:" not in rb.comparison_text(v, v)
