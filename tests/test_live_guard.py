"""Live portfolio guard maths (backtest/live_guard.py). Paper trading is never affected."""
from datetime import date, timedelta

from helpers import env

import backtest.live_guard as g

C = g.GuardConfig()
D = date(2026, 11, 2)


def B(open_=(), realised=()):
    return g.Book(list(open_), list(realised))


def test_defaults_are_the_owner_decisions():
    assert (C.capital, C.max_open, C.max_stock_pct, C.daily_loss_limit, C.monthly_loss_limit) == \
        (100000.0, 5, 20.0, 0.0, 6000.0)
    assert g.GuardConfig.from_env() == C


def test_per_stock_cap_20_percent():
    assert g.allowed_qty(C, B(), "TCS", 2000, 8, D) == (8, "")
    q, w = g.allowed_qty(C, B(), "TCS", 2000, 15, D)
    assert q == 10 and "reduced" in w
    assert g.allowed_qty(C, B([("TCS", 18000)]), "TCS", 2000, 8, D)[0] == 1
    q, w = g.allowed_qty(C, B([("TCS", 20000)]), "TCS", 2000, 8, D)
    assert q == 0 and "20%" in w


def test_max_open_and_capital():
    q, w = g.allowed_qty(C, B([("A", 19000)] * 5), "X", 100, 10, D)
    assert q == 0 and "max 5" in w
    assert g.allowed_qty(C, B([("A", 20000)] * 4), "X", 100, 300, D)[0] == 200
    assert g.allowed_qty(C, B([("A", 19900), ("B", 19900), ("C", 19900), ("D", 19950)]), "X", 1000, 30, D)[0] == 20
    q, w = g.allowed_qty(C, B([("A", 25000)] * 4), "X", 1000, 30, D)
    assert q == 0 and "capital" in w


def test_daily_limit_off_by_default_but_works_when_set():
    losses = [(D, -1200), (D, -900)]
    assert g.allowed_qty(C, B(realised=losses), "X", 100, 10, D) == (10, "")
    q, w = g.allowed_qty(g.GuardConfig(daily_loss_limit=2000), B(realised=losses), "X", 100, 10, D)
    assert q == 0 and "daily" in w


def test_monthly_limit_counts_only_this_month():
    assert g.allowed_qty(C, B(realised=[(D - timedelta(days=1), -1500)]), "X", 100, 10, D)[0] == 10
    r = [(date(2026, 11, 1), -3000), (date(2026, 10, 30), -9000), (date(2026, 11, 2), -1000)]
    assert g.allowed_qty(C, B(realised=r), "X", 100, 10, date(2026, 11, 3))[0] == 10
    r = [(date(2026, 11, 1), -3000), (date(2026, 11, 2), -1500), (date(2026, 11, 2), -400), (date(2026, 11, 1), -1200)]
    q, w = g.allowed_qty(C, B(realised=r), "X", 100, 10, date(2026, 11, 3))
    assert q == 0 and "monthly" in w


def test_nothing_to_buy():
    assert g.allowed_qty(C, B(), "X", 0, 10, D)[0] == 0
    assert g.allowed_qty(C, B(), "X", 100, 0, D)[0] == 0


def test_from_env_never_crashes_on_garbage():
    for k, v in (("LIVE_MAX_OPEN", "inf"), ("LIVE_CAPITAL", "1e999"), ("LIVE_MAX_STOCK_PCT", "nan"),
                 ("LIVE_MONTHLY_LOSS_LIMIT", "-5"), ("LIVE_MAX_OPEN", "0.5"), ("LIVE_CAPITAL", "50,000")):
        with env(**{k: v}):
            c = g.GuardConfig.from_env()
            assert c.capital == 100000 and 1 <= c.max_open <= 1000 and c.max_stock_pct == 20
            assert c.monthly_loss_limit == 6000
            assert g.config_problems(), (k, v)       # ...and it is reported, so BUYs are blocked


def test_dict_round_trip_and_bad_dict():
    c = g.GuardConfig(capital=50000, max_open=3, max_stock_pct=10, daily_loss_limit=0, monthly_loss_limit=3000)
    assert g.GuardConfig.from_dict(c.as_dict()) == c
    assert g.GuardConfig.from_dict(None) == C
    assert g.GuardConfig.from_dict({"capital": "x"}) == C


def test_simulate_caps_and_frees_positions():
    T = [{"rule": "r", "symbol": f"S{i}", "entry": 1000, "qty": 17, "entry_date": date(2026, 10, 14),
          "exit_date": date(2026, 10, 28), "pnl": 100.0} for i in range(7)]
    s = g.simulate(T, C)
    assert s["taken"] == 5 and s["skipped"] == 2 and s["pnl_with_guard"] == 500 and s["pnl_without"] == 700
    T.append({"rule": "r", "symbol": "Z", "entry": 1000, "qty": 17, "entry_date": date(2026, 10, 29),
              "exit_date": None, "pnl": None})
    s = g.simulate(T, C)
    assert s["taken"] == 6 and s["open_value_now"] == 17000
