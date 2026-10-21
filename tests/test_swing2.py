"""Engine 2 (Swing 2.0) — synthetic data only."""
import random
from datetime import date

from helpers import bar, trading_days

from backtest import nifty50_history as nh
from backtest import portfolio15 as pf
from backtest import swing2 as s2

DAYS = trading_days(date(2022, 1, 3), 900)
SYMS = list(nh.CURRENT[:30])


def _series(sym):
    rnd, out = random.Random(sym), []
    p = 100.0 + sum(map(ord, sym)) % 40
    drift = 0.0012 if sym in SYMS[:6] else 0.0001
    for k, d in enumerate(DAYS):
        o = p
        shock = -0.03 if (k % 37 == 0 and sym in SYMS[:6]) else 0.0      # regular pullbacks in leaders
        p = o * (1 + drift + shock + rnd.gauss(0, 0.012))
        out.append(bar(d, o, max(o, p) * 1.004, min(o, p) * 0.996, p, sym, 90000))
    return out


class Loader:
    def get_historical_bars(self, sym, start, end, interval="1d"):
        return [b for b in _series(sym) if start.date() <= b.timestamp.date() < end.date()]


def _nifty(drift):
    return [(d, 20000 * (1 + drift) ** i) for i, d in enumerate(DAYS)]


def _run(drift=0.0005):
    u, mkt, start, errors = pf.load(SYMS, DAYS[-1], {}, loader=Loader(), nifty=_nifty(drift), eval_days=700)
    pools = {"S50": lambda d: SYMS, "S200": lambda d: SYMS}
    return s2.run(u, mkt, start, pools), u, start


def test_rows_verdicts_and_choice_rule():
    res, _, _ = _run()
    names = [r["strategy"] for r in res["rows"]]
    assert names == ["FD 7%", "NIFTY buy & hold", "S50 W-off", "S50 W-half", "S50 W-stop",
                     "S200 W-off", "S200 W-half", "S200 W-stop"]
    judged = [r for r in res["rows"] if "verdict" in r]
    assert len(judged) == 6 and all("beats_nifty" in r["verdict"] for r in judged)
    s50_pass = [r for r in judged if r["strategy"].startswith("S50") and r["verdict"]["pass"]]
    assert (res["chosen"] is None) == (not s50_pass)
    if s50_pass:
        assert res["chosen"] == max(s50_pass, key=lambda r: r["full"]["ratio"])["strategy"]


def test_weak_stop_buys_nothing_in_a_falling_market():
    res, _, _ = _run(drift=-0.0008)
    rows = {r["strategy"]: r for r in res["rows"]}
    assert rows["S50 W-stop"]["trades"] == 0
    assert rows["S50 W-off"]["trades"] > 0
    assert rows["S50 W-off"]["trade_stats"]["weak_trades"] == rows["S50 W-off"]["trades"]


def test_never_more_than_five_positions():
    _, u, start = _run()
    i0 = max(s2.bisect_right(u.dates, start) - 1, 0)
    sim = s2.simulate(u, i0, lambda d: SYMS, 15, 1.0)
    ev = []
    for t in sim["trades"]:
        ev += [(t["entry_date"], 1), (t["exit_date"], -1)]
    cur = peak = 0
    for _, k in sorted(ev, key=lambda e: (e[0], e[1])):
        cur += k
        peak = max(peak, cur)
    assert sim["trades"] and peak <= s2.MAX_OPEN and all(v > 0 for _, v in sim["curve"])
    assert {t["reason"] for t in sim["trades"]} <= {"BOUNCE", "TIME", "STOP", "STOP_GAP", "NO_DATA"}


def test_entry_signal_rules():
    days = trading_days(date(2024, 1, 1), 260)
    up = [bar(d, 100 + k * 0.3, 101 + k * 0.3, 99 + k * 0.3, 100 + k * 0.3) for k, d in enumerate(days)]
    u = pf.Universe([(d, 1.0) for d in days], {"X": up})
    assert s2.entry_signal(u, "X", 259) is None                     # no pullback
    pull = up[:-1] + [bar(days[-1], 170, 170, 165, 166)]             # ~6% below the 10-day high, above SMA200
    u = pf.Universe([(d, 1.0) for d in days], {"X": pull})
    assert s2.entry_signal(u, "X", 259) is not None
    crash = up[:-1] + [bar(days[-1], 120, 120, 100, 100)]            # below the 200-day average
    u = pf.Universe([(d, 1.0) for d in days], {"X": crash})
    assert s2.entry_signal(u, "X", 259) is None
    assert s2.entry_signal(pf.Universe([(d, 1.0) for d in days[:50]], {"X": up[:50]}), "X", 49) is None


def test_research_card():
    import garud_research as gr
    p = {"start": "2011", "end": "2026", "chosen": None, "passed": ["S200 W-off"],
         "rows": [{"strategy": "S50 W-stop", "full": {"cagr": 5.0, "max_dd": 20.0, "final": 200000},
                   "verdict": {"pass": False}}]}
    c = gr.swing2_summary(p)
    assert not c["pass"] and "S50" in c["verdict"] and "Swing 2.0" in c["title"]
    assert [k for k, _, _ in gr.study_cards({})][0] == "SWING2_15Y"
