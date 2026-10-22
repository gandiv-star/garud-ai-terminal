"""M2 robustness check — synthetic data, no download."""
from datetime import date

from helpers import trading_days

from backtest import m2_robustness as rb
from backtest import momentum200 as m2
import test_momentum200 as tm


def _bench(drift):
    return [(d, 100 * (1 + drift) ** i) for i, d in enumerate(tm.DAYS)]


def test_six_variants_and_verdict():
    data, start, _ = m2.load(tm.SYMS, tm.END, {}, loader=tm.Loader(), nifty=tm._nifty(0.0004), eval_days=900)
    res = rb.run(data, start, lambda d: tm.SYMS, {"NIFTY 200 index": _bench(0.0003), "ETF": []})
    names = [r["strategy"] for r in res["rows"]]
    assert names == [v[0] for v in rb.VARIANTS]
    assert res["passed_count"] == sum(r["verdict"]["pass"] for r in res["rows"])
    assert res["robust"] == (res["passed_count"] >= rb.ROBUST_MIN_PASS)
    q = next(r for r in res["rows"] if r["strategy"] == "top20 quarterly")
    mth = next(r for r in res["rows"] if r["strategy"] == "top20 monthly (M2)")
    assert q["trades"] <= mth["trades"]
    b = {x["name"]: x for x in res["benchmarks"]}
    assert b["NIFTY 200 index"]["available"] and b["NIFTY 200 index"]["m2_cagr_same_period"] is not None
    assert b["ETF"]["available"] is False


def test_base_variant_matches_engine1_m2():
    data, start, _ = m2.load(tm.SYMS, tm.END, {}, loader=tm.Loader(), nifty=tm._nifty(0.0004), eval_days=900)
    res = rb.run(data, start, lambda d: tm.SYMS)
    e1 = m2.run(data, start, lambda d: tm.SYMS, lambda d: frozenset(tm.SYMS[:20]))
    base = next(r for r in res["rows"] if r["strategy"] == "top20 monthly (M2)")
    m2row = next(r for r in e1["rows"] if r["strategy"].startswith("M2"))
    assert base["full"] == m2row["full"] and base["trades"] == m2row["trades"]


def test_monthly_returns_sharpe_bootstrap():
    days = trading_days(date(2020, 1, 1), 800)
    curve = [(d, 100 * 1.0004 ** i) for i, d in enumerate(days)]
    rets = rb.monthly_returns(curve)
    assert len(rets) >= 35 and all(r > 0 for r in rets)
    sh, so = rb.sharpe_sortino(rets)
    assert sh is not None and so is None or so > 0                    # no losing month -> Sortino undefined/large
    b = rb.bootstrap(rets, 3.0, n=500)
    assert b["p_below_fd"] == 0.0 and b["cagr_p5"] > 7
    assert b["p_dd_over_25"] == 0.0                                   # never a losing month -> no drawdown
    crash = rb.bootstrap([0.05] * 20 + [-0.30] * 5, 2.0, n=500)
    assert crash["p_dd_over_25"] > 50
    assert rb.bootstrap(rets[:5], 1.0)["p_below_fd"] is None
    assert rb.series_cagr(curve, days[0], days[-1])[0] > 0
    assert rb.series_cagr(curve[:10], days[0], days[9])[0] is None


def test_research_card():
    import garud_research as gr
    p = {"start": "2011", "end": "2026", "robust": False, "passed_count": 3,
         "rows": [{"strategy": "top10 monthly", "full": {"cagr": 20, "max_dd": 30}, "sharpe": 0.9,
                   "verdict": {"pass": False}}],
         "bootstrap": {"p_below_fd": 4.2, "cagr_p5": 9.1}, "benchmarks": [
             {"name": "NIFTY 200 index", "available": True, "cagr": 12.0, "m2_cagr_same_period": 20.0,
              "from": "2011", "to": "2026"}]}
    c = gr.m2_robustness_summary(p)
    assert not c["pass"] and "3/6" in c["verdict"] and len(c["lines"]) == 3
    assert "M2_ROBUSTNESS" in [k for k, _, _ in gr.study_cards({})]
