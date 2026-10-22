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
    assert s1["units"]["A"] in (249, 250) and "MRF" not in s1["units"]   # MRF > 2x the 25,000 slot
    assert all(isinstance(q, int) for q in s1["units"].values()) and s1["cash"] >= 0
    assert 99000 < s1["value"] <= mp.CAPITAL
    assert st["units"] == {} and st["cash"] == mp.CAPITAL                # input untouched
    s2 = mp.rebalance(s1, {k: v * 1.01 for k, v in prices.items()}, want, date(2026, 12, 1))
    assert not [t for t in s2["trades"] if t["symbol"] != "MRF"]         # inside the 2% band: no churn
    s3 = mp.rebalance(s1, prices, {"A": 0.25, "B": 0.25}, date(2026, 12, 1))
    assert "C" not in s3["units"] and any(t["side"] == "SELL" and t["symbol"] == "C" for t in s3["trades"])
    s4 = mp.rebalance(s1, prices, {}, date(2026, 12, 1), allow_buys=False)
    assert s4["units"] == {} and all(t["side"] == "SELL" for t in s4["trades"])


def test_capital_per_portfolio():
    assert mp.capital_of("M2") == 300000 and mp.capital_of("G") == 100000
    assert mp.initial_state("M2")["cash"] == 300000


def test_leftover_cash_tops_up_toward_target():
    st = mp.initial_state("X")                                  # Rs.1,00,000
    prices = {"A": 2600.0, "B": 30000.0, "C": 60000.0, "D": 100.0}
    s1 = mp.rebalance(st, prices, {s: 0.25 for s in prices}, NOV2)
    assert s1["units"]["A"] == 10                                # 25,000 slot: 9 fit, 10th is closer to target
    assert s1["units"]["B"] == 1                                 # above the slot but under 2x: one share
    assert "C" not in s1["units"]                                # more than 2x the slot: stays cash
    assert s1["cash"] >= 0 and s1["value"] <= mp.CAPITAL
    for s, q in s1["units"].items():
        assert abs(q * prices[s] - 25000) <= abs((q - 1) * prices[s] - 25000) or q == 1


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
        cap = mp.capital_of(p["portfolio"])
        assert p["units"] and p["cash"] >= 0 and 0.97 * cap < p["value"] <= cap
        assert p["cash"] < 0.05 * cap                                     # money is actually invested
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
    assert "month-end 30 Sep" in sent[0] and "buying-path check" in sent[0] and "BUY: —" not in sent[0].split("buying-path")[1]
    assert mp.START_SIGNAL == start_before                     # real start date restored


def test_dry_run_weak_market_still_checks_buying():
    sent = []
    falling = [(d, 20000 * 0.999 ** i) for i, d in enumerate(DAYS)]

    def load():
        return m2.load(nh.CURRENT, date(2026, 10, 20), {}, loader=Loader(),
                       nifty=[x for x in falling if x[0] <= date(2026, 10, 20)], eval_days=30)
    code = rmp.dry_run(datetime(2026, 10, 21, 13, 0, tzinfo=IST), sent.append,
                       nifty=[x for x in falling if x[0] <= date(2026, 10, 21)], load_fn=load, closes_fn=_closes)
    real, check = sent[0].split("buying-path check")
    assert code == 0 and "liquid fund" in real and "BUY: —" in real and "BUY: —" not in check


def test_rebalance_message_shows_sector_concentration():
    db = FakeDB()
    r = _run(db, datetime(2026, 11, 2, 17, 0, tzinfo=IST))
    assert any(ln.strip().startswith("sectors:") for ln in r["lines"])


def test_stale_data_blocks_rebalance():
    db = FakeDB()
    nifty = [x for x in NIFTY if x[0] <= NOV2]
    r = rmp.run(db, datetime(2026, 11, 12, 17, 0, tzinfo=IST), nifty=nifty, load_fn=_load, closes_fn=_closes)
    assert not db.of(mp.EV_REBAL) and any("stale" in e for e in r["errors"])


def test_drawdown_alert():
    db = FakeDB()
    st = {**mp.initial_state("G"), "as_of": "2026-11-02", "units": {"X": 100}, "cash": 0.0,
          "last_px": {"X": 1000.0}, "value": 100000.0, "month": "2026-10"}
    db.add(mp.EV_REBAL, st)
    db.add(mp.EV_NAV, {"portfolio": "G", "date": "2026-11-02", "value": 100000.0, "nifty": 1.0})
    nifty = [x for x in NIFTY if x[0] <= NOV3]
    r = rmp.run(db, datetime(2026, 11, 3, 17, 0, tzinfo=IST), nifty=nifty, load_fn=_load,
                closes_fn=lambda syms, day: {"X": 800.0})
    assert any("G is 20.0% below its peak" in e for e in r["errors"]), r["errors"]


def test_sectors_map():
    from backtest import sectors
    assert len(sectors.INDUSTRY) == 200 and sectors.industry("TCS") == "Information Technology"
    assert sectors.industry("UNKNOWN") == "Other"
    assert sectors.concentration({"TCS": 30, "INFY": 30, "SBIN": 40}) == [("Information Technology", 60.0),
                                                                        ("Financial Services", 40.0)]
    assert sectors.concentration({}) == []


def _main_with_fakes(monkey_env, now_days, manual=False):
    """Runs run_momentum_paper.main() end to end with a fake database and fake NIFTY data."""
    import sys
    import types
    from helpers import env
    fake_db = FakeDB()
    mod = types.ModuleType("database.db")

    class Database:
        def __init__(self, settings):
            pass

        def connect(self):
            pass

        def __getattr__(self, name):
            return getattr(fake_db, name)
    mod.Database = Database
    saved = sys.modules.get("database.db")
    sys.modules["database.db"] = mod
    sent = []
    try:
        import backtest.run_rule_paper as rp
        old_send, old_series = rp.send_telegram, rmp._nifty_series
        rp.send_telegram = sent.append
        rmp._nifty_series = lambda a, b: [(d, 25000.0) for d in now_days]
        with env(DATABASE_URL="postgresql://fake", RUN_SOURCE="manual" if manual else "schedule"):
            code = rmp.main()
    finally:
        rp.send_telegram, rmp._nifty_series = old_send, old_series
        if saved is not None:
            sys.modules["database.db"] = saved
        else:
            sys.modules.pop("database.db", None)
    return code, sent


def test_main_completes_scheduled_and_manual():
    """Regression: a stray line in main() crashed every automatic run on 21 Oct 2026."""
    days = [d for d in DAYS if d <= date(2026, 10, 21)]
    code, sent = _main_with_fakes(None, days)
    assert code == 0
    code, sent = _main_with_fakes(None, days, manual=True)
    assert code == 0 and sent and "starts with the 30 Oct 2026" in sent[0]


def test_days_below_peak():
    import garud_research as gr
    rebals = [{"portfolio": "G", "fill_date": "2026-11-02", "value": 100000.0, "units": {"A": 1}}]
    navs = [{"portfolio": "G", "date": "2026-11-02", "value": 100000.0},
            {"portfolio": "G", "date": "2026-11-05", "value": 104000.0},
            {"portfolio": "G", "date": "2026-11-20", "value": 98800.0}]
    r = gr.momentum_paper_rows(rebals, navs, {"G": "G"}, {"G": 100000.0})[0]
    assert r["dd_now"] == 5.0 and r["days_below_peak"] == 15 and r["max_dd"] == 5.0
    navs.append({"portfolio": "G", "date": "2026-11-25", "value": 105000.0})
    r = gr.momentum_paper_rows(rebals, navs, {"G": "G"}, {"G": 100000.0})[0]
    assert r["dd_now"] == 0.0 and r["days_below_peak"] == 0
