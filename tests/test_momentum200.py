"""Engine 1 (Momentum 200) — synthetic data only, no download."""
import random
from datetime import date

from helpers import bar, trading_days

from backtest import longterm as lt
from backtest import momentum200 as m2

DAYS = trading_days(date(2021, 1, 4), 1100)
END = DAYS[-1]
SYMS = [f"S{i:02d}" for i in range(40)]


def _series(sym, drift, noise=0.015):
    rnd, p, out = random.Random(sym), 100.0, []
    for d in DAYS:
        o = p
        p = o * (1 + drift + rnd.gauss(0, noise))
        out.append(bar(d, o, max(o, p) * 1.003, min(o, p) * 0.997, p, sym, 50000 + rnd.randint(0, 50000)))
    return out


class Loader:
    def get_historical_bars(self, sym, start, end, interval="1d"):
        if sym == "GONE":
            raise RuntimeError("no data")
        strong = sym in ("S01", "S02", "S03")
        return [b for b in _series(sym, 0.002 if strong else 0.0002, 0.005 if strong else 0.015) if start.date() <= b.timestamp.date() < end.date()]


def _nifty(drift):
    return [(d, 20000 * (1 + drift) ** i) for i, d in enumerate(DAYS)]


def _run(nifty_drift=0.0004):
    data, start, errors = m2.load(SYMS + ["GONE"], END, {}, loader=Loader(), nifty=_nifty(nifty_drift),
                                  eval_days=900)
    return m2.run(data, start, lambda d: SYMS + ["GONE"], lambda d: frozenset(SYMS[:20])), data, errors


def test_rows_and_verdicts():
    res, _, errors = _run()
    names = [r["strategy"] for r in res["rows"]]
    assert names[:2] == ["FD 7%", "NIFTY buy & hold"]
    judged = [r for r in res["rows"] if "verdict" in r]
    assert [r["strategy"].split()[0] for r in judged] == ["M1", "M2", "G"]
    assert all(set(r["verdict"]) >= {"beats_fd", "dd_ok", "pass", "beats_nifty"} for r in judged)
    assert "GONE" in errors and res["bias_note"]


def test_ranking_prefers_strong_stocks_and_respects_liquidity_cap():
    _, data, _ = _run()
    i = len(data.mkt.dates) - 1
    ranked = m2.ranking(data, i, SYMS)
    assert set(ranked[:3]) == {"S01", "S02", "S03"}
    assert len(ranked) <= m2.LIQUID_TOP


def test_weak_switch_holds_liquid_fund():
    res, _, _ = _run(nifty_drift=-0.0008)
    m2row = next(r for r in res["rows"] if r["strategy"].startswith("M2"))
    assert m2row["trades"] == 0 and 6.0 < m2row["full"]["cagr"] < 7.0


def test_buffer_keeps_holdings_inside_top30():
    _, data, _ = _run()
    fn = m2.momentum_targets(data, lambda d: SYMS, weak_switch=False)
    i = len(data.mkt.dates) - 1
    first = set(fn(i - 21))
    second = set(fn(i))
    ranked = m2.ranking(data, i, SYMS)
    kept = first & second
    assert all(ranked.index(s) < m2.KEEP_RANK for s in kept)
    assert len(second) == m2.TOP_N


def test_score_needs_a_year_of_history():
    _, data, _ = _run()
    assert data.score_inputs("S01", 100) is None
    assert data.score_inputs("S01", len(data.mkt.dates) - 1) is not None


def test_universe_list():
    assert len(m2.NIFTY200_TODAY) == 200 and len(set(m2.NIFTY200_TODAY)) == 200


def test_research_card():
    import garud_research as gr
    p = {"start": "2011", "end": "2026", "passed": [],
         "rows": [{"strategy": "M1 Momentum 200", "full": {"cagr": 6.0, "max_dd": 30.0, "final": 200000},
                   "verdict": {"pass": False}}]}
    c = gr.momentum200_summary(p)
    assert "Momentum 200" in c["title"] and not c["pass"] and "NIFTY 200" in c["lines"][-1][1]
