"""Monthly momentum PAPER portfolios — fake database and synthetic prices only."""
import random
from datetime import date, datetime

from helpers import IST, FakeDB, bar, trading_days

from backtest import momentum200 as m2
from backtest import momentum_paper as mp
from backtest import nifty50_history as nh
from backtest import run_momentum_paper as rmp

DAYS = trading_days(date(2025, 6, 2), 380)          # weekdays up to mid-Nov 2026
OCT30, NOV2, NOV3 = date(2026, 10, 30), date(2026, 11, 2), date(2026, 11, 3)


def test_calendar_has_the_days_we_need():
    assert OCT30 in DAYS and NOV2 in DAYS and DAYS.index(NOV2) == DAYS.index(OCT30) + 1


def test_due_month_ends_and_completed_close():
    d = [x for x in DAYS if date(2026, 10, 26) <= x <= NOV2]
    last = mp.completed_dates(d, datetime(2026, 11, 2, 12, 0, tzinfo=IST))
    assert d[last] == OCT30                                   # 2 Nov close not final at noon
    assert mp.due_month_ends(d, last, None) == []             # fill day not complete yet
    last = mp.completed_dates(d, datetime(2026, 11, 2, 17, 0, tzinfo=IST))
    assert d[last] == NOV2 and [d[m] for m in mp.due_month_ends(d, last, None)] == [OCT30]
    assert mp.due_month_ends(d, last, "2026-10") == []        # already done
    sept = [x for x in DAYS if date(2026, 9, 28) <= x <= date(2026, 10, 2)]
    assert mp.due_month_ends(sept, len(sept) - 1, None) == []  # before the start date: nothing


def test_rebalance_whole_shares_band_and_sells():
    st = mp.initial_state("X")
    prices = {"A": 100.0, "B": 250.0, "C": 1000.0, "MRF": 140000.0}
    want = {s: 0.25 for s in prices}
    s1 = mp.rebalance(st, prices, want, NOV2)
    assert s1["units"]["A"] == 249 and "MRF" not in s1["units"]          # 25,000 slot < one MRF share
    assert all(isinstance(q, int) for q in s1["units"].values()) and s1["cash"] >= 0
    assert 99000 < s1["value"] <= mp.CAPITAL
    assert st["units"] == {} and st["cash"] == mp.CAPITAL                # input untouched
    s2 = mp.rebalance(s1, {k: v * 1.01 for k, v in prices.items()}, want, date(2026, 12, 1))
    assert not [t for t in s2["trades"] if t["symbol"] != "MRF"]         # inside the 2% band: no churn
    s3 = mp.rebalance(s1, prices, {"A": 0.25, "B": 0.25}, date(2026, 12, 1))
    assert "C" not in s3["units"] and any(t["side"] == "SELL" and t["symbol"] == "C" for t in s3["trades"])
    s4 = mp.rebalance(s1, prices, {}, date(2026, 12, 1), allow_buys=False)
    assert s4["units"] == {} and all(t["side"] == "SELL" for t in s4["trades"])


def test_cash_earns_liquid_rate():
    st = {**mp.initial_state("X"), "as_of": "2026-01-01"}
    assert abs(mp.mark(st, {}, date(2027, 1, 1)) - mp.CAPITAL * 1.065) < 1


def _series(sym):
    rnd, out = random.Random(sym), []
    p = 100.0 + sum(map(ord, sym)) % 50
    strong = sym in ("TRENT", "BEL", "HAL", "INFY")
    drift, noise = (0.004, 0.006) if strong else (0.0002, 0.012)
    for d in DAYS:
        o = p
        p = o * (1 + drift + rnd.gauss(0, noise))
        out.append(bar(d, o, max(o, p) * 1.003, min(o, p) * 0.997, p, sym, 80000))
    return out


class Loader:
    def get_historical_bars(self, sym, start, end, interval="1d"):
        return [b for b in _series(sym) if start.date() <= b.timestamp.date() < end.date()]


NIFTY = [(d, 20000 * 1.0004 ** i) for i, d in enumerate(DAYS)]


def _load():
    return m2.load(nh.CURRENT + ("TRENT", "HAL"), NOV2, {}, loader=Loader(), nifty=[x for x in NIFTY if x[0] <= NOV2],
                   eval_days=30)


def _closes(symbols, day):
    out = {}
    for s in symbols:
        b = [x for x in _series(s) if x.timestamp.date() <= day]
        out[s] = b[-1].close
    return out


def _run(db, now):
    nifty = [x for x in NIFTY if x[0] <= now.date()]
    return rmp.run(db, now, nifty=nifty, load_fn=_load, closes_fn=_closes)


def test_end_to_end_first_rebalance_then_daily_value():
    db = FakeDB()
    r = _run(db, datetime(2026, 10, 30, 17, 0, tzinfo=IST))
    assert not r["activity"] and not db.of(mp.EV_REBAL)                 # signal day: wait for next close
    r = _run(db, datetime(2026, 11, 2, 17, 0, tzinfo=IST))
    assert r["activity"] and not r["errors"], r
    reb = db.of(mp.EV_REBAL)
    assert {p["portfolio"] for p in reb} == {"M2", "G"}
    for p in reb:
        assert p["signal_date"] == "2026-10-30" and p["fill_date"] == "2026-11-02" and p["month"] == "2026-10"
        assert p["units"] and p["cash"] >= 0 and 95000 < p["value"] <= 100000
    m2p = next(p for p in reb if p["portfolio"] == "M2")
    assert len(m2p["units"]) <= m2.TOP_N and {"TRENT", "BEL", "HAL", "INFY"} <= set(m2p["units"])
    assert len(next(p for p in reb if p["portfolio"] == "G")["units"]) <= 10
    n_nav = len(db.of(mp.EV_NAV))
    r = _run(db, datetime(2026, 11, 2, 17, 30, tzinfo=IST))                # repeat run: nothing new
    assert not r["activity"] and len(db.of(mp.EV_REBAL)) == 2 and len(db.of(mp.EV_NAV)) == n_nav
    _run(db, datetime(2026, 11, 3, 17, 0, tzinfo=IST))
    navs = [p for p in db.of(mp.EV_NAV) if p["date"] == "2026-11-03"]
    assert {p["portfolio"] for p in navs} == {"M2", "G"} and all(p["value"] > 0 and p["nifty"] for p in navs)


def test_kill_switch_means_no_buys():
    db = FakeDB()
    rmp.run(db, datetime(2026, 11, 2, 17, 0, tzinfo=IST), kill=True,
            nifty=[x for x in NIFTY if x[0] <= NOV2], load_fn=_load, closes_fn=_closes)
    for p in db.of(mp.EV_REBAL):
        assert p["units"] == {} and p["kill_switch"] and p["value"] == p["cash"]


def test_status_and_research_rows():
    db = FakeDB()
    assert "starts with the 30 Oct 2026" in rmp.status_lines(db)[0]
    _run(db, datetime(2026, 11, 2, 17, 0, tzinfo=IST))
    _run(db, datetime(2026, 11, 3, 17, 0, tzinfo=IST))
    assert all("Rs." in ln for ln in rmp.status_lines(db))
    import garud_research as gr
    rows = gr.momentum_paper_rows(db.of(mp.EV_REBAL), db.of(mp.EV_NAV), mp.PORTFOLIOS)
    assert [r["id"] for r in rows] == ["M2", "G"] and all(r["started"] and r["holdings"] for r in rows)
    assert gr.momentum_paper_rows([], [], mp.PORTFOLIOS)[0]["started"] is False


def test_dry_run_saves_nothing_and_reports_ok():
    sent = []
    start_before = mp.START_SIGNAL
    nifty = [x for x in NIFTY if x[0] <= date(2026, 10, 21)]

    def load():
        return m2.load(nh.CURRENT, date(2026, 10, 20), {}, loader=Loader(),
                       nifty=[x for x in NIFTY if x[0] <= date(2026, 10, 20)], eval_days=30)
    code = rmp.dry_run(datetime(2026, 10, 21, 13, 0, tzinfo=IST), sent.append, nifty=nifty, load_fn=load,
                       closes_fn=_closes)
    assert code == 0 and "DRY RUN" in sent[0] and "Dry run OK" in sent[0], sent
    assert "month-end 30 Sep" in sent[0]
    assert mp.START_SIGNAL == start_before                     # real start date restored
