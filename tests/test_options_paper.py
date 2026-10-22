"""Options paper test (weekly NIFTY iron condor) — no orders, fake option chain."""
import math
from datetime import date, datetime, time

from helpers import FakeDB

import backtest.options_paper as op

IST = op.IST


def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _bs(spot, k, t, vol, cp):
    if t <= 0:
        return (max(spot - k, 0), 1.0 if spot > k else 0.0) if cp == "CE" else (max(k - spot, 0), -1.0 if spot < k else 0.0)
    d1 = (math.log(spot / k) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if cp == "CE":
        return spot * _ncdf(d1) - k * _ncdf(d2), _ncdf(d1)
    return k * _ncdf(-d2) - spot * _ncdf(-d1), _ncdf(d1) - 1


class Data:
    def __init__(self):
        self.spot, self.vol, self.calls, self.fail = 25000.0, 0.13, 0, False
        self.expiries = [date(2026, 10, 20), date(2026, 10, 27), date(2026, 11, 3)]

    def contracts(self):
        if self.fail:
            raise RuntimeError("HTTP 401")
        return [{"expiry": str(e), "lot_size": 75} for e in self.expiries]

    def chain(self, expiry, now=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("HTTP 401")
        t = max((datetime.combine(expiry, time(15, 30), IST) - self.now).total_seconds() / 86400 / 365, 0)
        rows = []
        for k in range(23000, 27050, 50):
            row = {"strike_price": k, "underlying_spot_price": self.spot}
            for cp, key in (("CE", "call_options"), ("PE", "put_options")):
                p, d = _bs(self.spot, k, t, self.vol, cp)
                p = max(p, 0.05)
                row[key] = {"instrument_key": f"NSE_FO|{k}{cp}",
                            "market_data": {"bid_price": round(p * 0.99, 2), "ask_price": round(p * 1.01 + 0.05, 2),
                                            "ltp": round(p, 2)},
                            "option_greeks": {"delta": round(d, 4)}}
            rows.append(row)
        return rows


CLOSES = {}


def run(db, data, now, **kw):
    data.now = now
    return op.run(db, data, now, nifty_close_on=lambda d: CLOSES.get(d), is_trading_day=lambda d: d.weekday() < 5, **kw)


def entries(db):
    return db.of("OPT_ENTRY")


def exits(db):
    return db.of("OPT_EXIT")


def test_charges_sane():
    assert 20 < op.leg_charges(1000, True) < 26


def test_entry_window_structure_and_no_duplicate():
    db, data = FakeDB(), Data()
    run(db, data, datetime(2026, 10, 16, 13, 0, tzinfo=IST))
    assert not db.ev
    r = run(db, data, datetime(2026, 10, 19, 9, 40, tzinfo=IST))
    assert not db.ev and any("no expiry" in l for l in r.lines)
    run(db, data, datetime(2026, 10, 21, 9, 40, tzinfo=IST))
    e = entries(db)
    assert len(e) == 1 and e[0]["id"] == "IC-2026-10-27" and e[0]["lot"] == 75 and e[0]["credit"] > 0
    sc, sp, lc, lp = [l["strike"] for l in e[0]["legs"]]
    assert sc > 25000 > sp and lc == sc + 200 and lp == sp - 200
    assert e[0]["max_spread_pct"] is not None and e[0]["max_spread_pct"] > 0      # recorded, never blocks
    run(db, data, datetime(2026, 10, 21, 9, 55, tzinfo=IST))
    assert len(entries(db)) == 1


def test_stop_loss_and_no_reentry_same_expiry():
    db, data = FakeDB(), Data()
    run(db, data, datetime(2026, 10, 21, 9, 40, tzinfo=IST))
    n = len(db.ev)
    run(db, data, datetime(2026, 10, 22, 17, 0, tzinfo=IST))
    assert len(db.ev) == n
    data.spot = 25700
    run(db, data, datetime(2026, 10, 23, 9, 40, tzinfo=IST))
    ex = exits(db)
    assert ex and ex[0]["reason"] == "STOP_LOSS" and ex[0]["net_pnl"] < 0
    data.spot = 25000
    r = run(db, data, datetime(2026, 10, 23, 9, 55, tzinfo=IST))
    assert any("already traded" in l for l in r.lines)
    assert not any("annualised" in l for l in r.lines)      # 1 condor: no yearly figure yet


def test_take_profit():
    db, data = FakeDB(), Data()
    run(db, data, datetime(2026, 10, 28, 9, 40, tzinfo=IST))
    for day in (29, 30):
        run(db, data, datetime(2026, 10, day, 11, 10, tzinfo=IST))
    run(db, data, datetime(2026, 11, 2, 11, 10, tzinfo=IST))
    ex = exits(db)
    assert ex and ex[0]["reason"] == "TAKE_PROFIT" and ex[0]["net_pnl"] > 0


def test_settled_from_nifty_close_when_runs_missed():
    db, data = FakeDB(), Data()
    run(db, data, datetime(2026, 10, 28, 9, 40, tzinfo=IST))
    e = entries(db)[0]
    data.fail = True
    r = run(db, data, datetime(2026, 11, 2, 11, 10, tzinfo=IST))
    assert r.errors and not exits(db)
    CLOSES[date(2026, 11, 3)] = e["legs"][0]["strike"] + 50
    r = run(db, data, datetime(2026, 11, 4, 9, 40, tzinfo=IST))
    ex = exits(db)[0]
    assert ex["reason"] == "SETTLED" and ex["debit"] == 50.0
    assert abs(ex["net_pnl"] - round((e["credit"] - 50) * 75 - e["entry_charges"], 2)) < 0.01
    assert any("options entry" in x for x in r.errors)


def test_circuit_breaker_and_kill_switch():
    db = FakeDB()
    for i in range(4):
        db.add("OPT_EXIT", {"rule": op.RULE_ID, "id": f"x{i}", "net_pnl": -4000})
    r = run(db, Data(), datetime(2026, 10, 28, 9, 40, tzinfo=IST))
    assert any("paused" in l for l in r.lines) and not entries(db)
    db2 = FakeDB()
    run(db2, Data(), datetime(2026, 10, 28, 9, 40, tzinfo=IST), allow_entries=False)
    assert not db2.ev


def test_net_premium_sign_open_and_close():
    """Shorts minus longs both when opening (credit) and closing (debit) — the bug fixed 16 Oct."""
    legs = [{"side": -1}, {"side": -1}, {"side": 1}, {"side": 1}]     # short call, short put, long wings
    prices = [50.0, 40.0, 10.0, 8.0]
    assert op.net_premium(legs, prices, opening=True) == 72.0
    assert op.net_premium(legs, prices, opening=False) == 72.0


def test_verdict_maths():
    s = op.stats([{"net_pnl": 1500}] * 22 + [{"net_pnl": -2000}] * 8, date(2026, 1, 1), date(2026, 7, 1))
    assert s["verdict"] == "PASS"
