"""Phase 2 portfolio test engine — synthetic data only (no download)."""
import random
from datetime import date, datetime, timedelta

from helpers import IST, bar, trading_days

from backtest import longterm as lt
from backtest import portfolio15 as pf
from backtest.backtest_engine import FillModel
from strategies.registry import STRATEGY_REGISTRY

DAYS = trading_days(date(2023, 1, 2), 900)
END = DAYS[-1]
SYMS = [f"S{i:02d}" for i in range(12)]
TF = STRATEGY_REGISTRY["Trend Following"]


def _series(seed, drift, vol=0.015):
    rnd, p, out = random.Random(seed), 100.0, []
    for d in DAYS:
        o = p * (1 + rnd.gauss(0, 0.003))
        p = o * (1 + drift + rnd.gauss(0, vol))
        out.append(bar(d, o, max(o, p) * 1.004, min(o, p) * 0.996, p, str(seed), 100000))
    return out


class Loader:
    def __init__(self, drift=0.0006):
        self.drift = drift

    def get_historical_bars(self, sym, start, end, interval="1d"):
        if sym == "BROKEN":
            raise RuntimeError("no data")
        return [b for b in _series(sym, self.drift) if start.date() <= b.timestamp.date() < end.date()]


def _nifty(drift):
    return [(d, 20000 * (1 + drift) ** i) for i, d in enumerate(DAYS)]


def _run(nifty_drift=0.0005, eval_days=500):
    u, mkt, start, errors = pf.load(SYMS + ["BROKEN"], END, {}, loader=Loader(), nifty=_nifty(nifty_drift),
                                    eval_days=eval_days)
    return pf.run(u, mkt, start, lambda d: frozenset(SYMS + ["BROKEN"]), TF), errors, u, start


def test_full_run_has_every_candidate_and_verdict():
    res, errors, _, _ = _run()
    names = [r["strategy"] for r in res["rows"]]
    for n in ("A v3 swing portfolio", "A2 v3 swing + weak-market switch", "FD 7%", "NIFTY buy & hold",
              "C NIFTY ETF + weak-market switch", "F Momentum top-10 (true list)",
              "G Momentum + weak-market switch (true list)"):
        assert n in names, n
    judged = [r["strategy"] for r in res["rows"] if "verdict" in r]
    assert len(judged) == 5 and "FD 7%" not in judged and "NIFTY buy & hold" not in judged
    for r in res["rows"]:
        if "verdict" in r:
            assert set(r["verdict"]) >= {"beats_fd", "dd_ok", "pass", "beats_nifty"}
    assert "BROKEN" in errors
    assert res["rules"]["pass_cagr_gt"] == 7.0 and res["rules"]["pass_max_dd_le"] == 25.0


def test_shared_capital_limits_hold():
    _, _, u, start = _run()
    start_i = max(pf.bisect_right(u.dates, start) - 1, 0)
    sim = pf.simulate(u, start_i, lambda d: frozenset(SYMS), TF)
    assert sim["trades"] and all(v > 0 for _, v in sim["curve"])
    events = []
    for t in sim["trades"]:
        events += [(t["entry_date"], 1), (t["exit_date"], -1)]
    open_now = peak = 0
    for _, k in sorted(events, key=lambda e: (e[0], e[1])):
        open_now += k
        peak = max(peak, open_now)
    assert peak <= pf.MAX_OPEN
    for t in sim["trades"]:
        assert t["entry"] * t["qty"] <= pf.CAPITAL * 3        # sized off equity, never wild


def test_weak_market_switch_stays_out():
    """NIFTY falling the whole time -> never bull -> A2 never buys, A2 = cash at the liquid rate."""
    res, _, _, _ = _run(nifty_drift=-0.0008)
    a2 = next(r for r in res["rows"] if r["strategy"].startswith("A2"))
    assert a2["trades"] == 0
    assert 6.0 < a2["full"]["cagr"] < 7.0                     # liquid fund 6.5%


def test_gap_down_stop_fills_at_open():
    days = trading_days(date(2024, 1, 1), 300)
    bars = []
    for k, d in enumerate(days):
        p = 100 + k * 0.5                                       # steady uptrend -> trend signal
        bars.append(bar(d, p - 0.2, p + 0.6, p - 0.6, p, "X"))
    u0 = pf.Universe([(d, 20000 * 1.001 ** i) for i, d in enumerate(days)], {"X": bars})
    sim = pf.simulate(u0, 260, lambda d: frozenset({"X"}), TF)
    first = sim["trades"] or []
    # build the same universe with a gap-down 3 sessions after the first entry
    entry_i = 261
    gap_day = entry_i + 3
    ref = bars[gap_day - 1].close
    bars2 = list(bars)
    bars2[gap_day] = bar(days[gap_day], ref * 0.80, ref * 0.81, ref * 0.78, ref * 0.79, "X")
    u = pf.Universe([(d, 20000 * 1.001 ** i) for i, d in enumerate(days)], {"X": bars2})
    sim = pf.simulate(u, 260, lambda d: frozenset({"X"}), TF)
    t = sim["trades"][0]
    assert t["reason"] == "STOP_GAP" and t["exit"] == round(ref * 0.80 * (1 - FillModel().stop_slippage_pct / 100), 2)
    assert first == [] or first[0]["reason"] != "STOP_GAP"


def test_verdict_bar():
    assert pf.verdict({"cagr": 7.5, "max_dd": 24.0})["pass"] is True
    assert pf.verdict({"cagr": 7.0, "max_dd": 10.0})["pass"] is False
    assert pf.verdict({"cagr": 12.0, "max_dd": 25.1})["pass"] is False
    assert pf.verdict({"cagr": None, "max_dd": None})["pass"] is False


def test_clean_and_stitch_bars():
    d = trading_days(date(2024, 1, 1), 8)
    bl = [bar(x, 100, 101, 99, 100) for x in d]
    bl[3] = bar(d[3], 100, 400, 99, 350)                      # bad tick, undone next day
    assert len(pf.clean_bars(bl)) == 7
    old = [bar(x, 50, 51, 49, 50) for x in d[:5]]
    new = [bar(x, 100, 101, 99, 100) for x in d[4:]]
    st = pf.stitch_bars(new, old)
    assert len(st) == 8 and st[0].close == 100.0             # scaled so the join has no jump


def test_research_card():
    import garud_research as gr
    p = {"start": "2011-09-27", "end": "2026-09-25", "passed": ["G Momentum + weak-market switch (true list)"],
         "rows": [{"strategy": "FD 7%", "full": {"cagr": 7.0, "max_dd": 0.0, "final": 275903}},
                  {"strategy": "G Momentum + weak-market switch (true list)",
                   "full": {"cagr": 11.39, "max_dd": 17.06, "final": 504000}, "verdict": {"pass": True}}]}
    c = gr.portfolio_summary(p)
    assert c["pass"] and "Paper" in c["verdict"] and "✅ PASS" in c["lines"][1][0]
    kinds = [k for k, _, _ in gr.study_cards({"PORTFOLIO_15Y": (None, p)})]
    assert kinds.index("PORTFOLIO_15Y") < kinds.index("EVIDENCE_MATRIX")
