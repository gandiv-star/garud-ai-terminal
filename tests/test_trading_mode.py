"""Trading Mode engine (mode_v1): which rules may buy in today's NIFTY regime."""
from datetime import date

import backtest.trading_mode as tm
from backtest import paper_rule

R = paper_rule.RULES
UP = [10000 * 1.001 ** i for i in range(300)]
DOWN = [10000 * 0.999 ** i for i in range(300)]


def test_bull_market_trend_following_only():
    m = tm.decide(UP, date(2026, 10, 16), R)
    assert m["regime"] == "MODERATE_BULL" and m["mode"] == "TREND FOLLOWING"
    assert [t for t, _ in m["active"]] == ["v3 — Trend 40d NIFTY 50"] and len(m["rejected"]) == 2


def test_weak_bear_volatility_expansion():
    m = tm.decide(DOWN, date(2026, 10, 16), R)
    assert m["regime"] == "WEAK_BEAR" and m["mode"] == "VOLATILITY EXPANSION"
    assert [t for t, _ in m["active"]] == ["v1 — 8 stocks", "v2 — NIFTY 50"]
    assert "does not buy in WEAK_BEAR" in dict(m["rejected"])["v3 — Trend 40d NIFTY 50"]


def test_kill_switch_and_short_history_mean_no_trade():
    assert tm.decide(DOWN, date(2026, 10, 16), R, kill_switch=True)["mode"] == "NO TRADE"
    m = tm.decide(UP[:150], None, R)
    assert m["mode"] == "NO TRADE" and "too short" in m["reason"]


def test_weak_bull():
    wb = UP[:290] + [UP[289] * 0.995 ** i for i in range(1, 11)]
    m = tm.decide(wb, date(2026, 10, 16), R)
    assert m["regime"] == "WEAK_BULL" and m["mode"] == "TREND FOLLOWING"


def test_volatility_context():
    assert tm.context(UP)["vol20_pct"] < 0.01
