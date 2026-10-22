"""Paper-trading rules: definitions are frozen and the exit/sizing maths is unchanged."""
from datetime import date, datetime

from helpers import IST, UTC, bar, trade, trading_days

from backtest import paper_rule as pr

ENTRY = datetime(2026, 10, 5, 4, 0, tzinfo=UTC)     # 09:30 IST on Mon 5 Oct
DAYS = trading_days(date(2026, 10, 5), 15)
LATE = datetime(2026, 10, 30, 18, 0, tzinfo=IST)


def flat_bars(n=15, price=100.0):
    return [bar(d, price, price + 1, price - 1, price) for d in DAYS[:n]]


def test_rules_are_frozen():
    ids = [r.rule_id for r in pr.RULES]
    assert ids == ["volatility_expansion_rule_v1", "volatility_expansion_rule_v2_nifty50",
                   "trend_following_40d_rule_v3_nifty50"]
    v1, v2, v3 = pr.RULES
    assert len(v1.universe) == 8 and len(v2.universe) == 50 and v3.universe == v2.universe
    assert v1.allowed_regimes == v2.allowed_regimes == ("WEAK_BEAR", "SIDEWAYS")
    assert set(v3.allowed_regimes) == {"MODERATE_BULL", "WEAK_BULL", "SIDEWAYS", "WEAK_BEAR"}
    assert (v1.max_holding_days, v2.max_holding_days, v3.max_holding_days) == (10, 10, 40)
    for r in pr.RULES:
        assert (r.stop_atr_multiplier, r.risk_pct, r.capital, r.target_trades) == (2.0, 1.0, 100000.0, 30)
    assert pr.ENTRY_CUTOFF_IST.strftime("%H:%M") == "11:30"


def test_position_size_one_percent_risk():
    stop, qty = pr.position_size(pr.RULE_V2, 1000.0, 20.0)       # stop distance 40
    assert stop == 960.0 and qty == 25
    stop, qty = pr.position_size(pr.RULE_V2, 1000.0, None)       # no ATR -> 3% stop
    assert stop == 970.0 and qty == 33


def test_stop_exit_at_stop_price():
    bars = flat_bars()
    bars[3] = bar(DAYS[3], 99, 99, 90, 92)
    assert pr.rule_exit(ENTRY, 95.0, bars, 10, now=LATE) == ("STOP_LOSS", 95.0, DAYS[3])


def test_time_exit_after_holding_days():
    reason, price, d = pr.rule_exit(ENTRY, 50.0, flat_bars(), 10, now=LATE)
    assert reason == "TIME_BASED" and price == 100.0 and d == DAYS[10]


def test_no_exit_yet():
    assert pr.rule_exit(ENTRY, 50.0, flat_bars(5), 10, now=LATE) is None


def test_gap_down_fill_by_entry_day():
    """Decision B (22 Oct 2026): positions opened from 23 Oct 2026 fill a gap-down stop at the open;
    older positions keep the stop price (never re-priced)."""
    assert pr.GAP_AWARE_FROM == date(2026, 10, 23)
    bars = flat_bars()
    bars[2] = bar(DAYS[2], 88, 89, 85, 86)                      # opens 7 below the 95 stop
    assert pr.rule_exit(ENTRY, 95.0, bars, 10, now=LATE)[1] == 95.0           # entry 5 Oct: old basis
    assert pr.rule_exit(ENTRY, 95.0, bars, 10, now=LATE, gap_aware=True)[1] == 88.0
    new_days = trading_days(date(2026, 10, 23), 15)
    new_entry = datetime(2026, 10, 23, 4, 0, tzinfo=UTC)
    nb = [bar(d, 100, 101, 99, 100) for d in new_days]
    nb[2] = bar(new_days[2], 88, 89, 85, 86)
    late = datetime(2026, 11, 30, 18, 0, tzinfo=IST)
    assert pr.rule_exit(new_entry, 95.0, nb, 10, now=late)[1] == 88.0       # new trade: at the open
    nb[2] = bar(new_days[2], 97, 98, 93, 94)                    # no gap: stop price either way
    assert pr.rule_exit(new_entry, 95.0, nb, 10, now=late)[1] == 95.0


def test_completed_bars_drops_todays_forming_bar():
    bars = flat_bars(3)
    during = datetime.combine(DAYS[2], datetime.min.time()).replace(hour=11, tzinfo=IST)
    after = during.replace(hour=16)
    assert len(pr.completed_bars(bars, during)) == 2 and len(pr.completed_bars(bars, after)) == 3


def test_time_exit_due_today():
    """Entry day 0; the 10th full day after entry is day 10 -> its close is the exit, so the
    broker SELL is sent before that close."""
    bars = flat_bars(11)
    now = datetime.combine(DAYS[10], datetime.min.time()).replace(hour=14, minute=40, tzinfo=IST)
    assert pr.time_exit_due_today(ENTRY, 50.0, bars, 10, now) is True
    assert pr.time_exit_due_today(ENTRY, 50.0, bars[:10], 10, now) is False     # no bar for today yet
    day9 = datetime.combine(DAYS[9], datetime.min.time()).replace(hour=14, minute=40, tzinfo=IST)
    assert pr.time_exit_due_today(ENTRY, 50.0, bars[:10], 10, day9) is False


def test_rule_already_used():
    t = trade("TCS", rule=pr.RULE_V2.rule_id, entered=ENTRY)
    assert pr.rule_already_used([t], pr.RULE_V2.rule_id, "TCS", DAYS[5]) == "open position exists"
    t.exit_price, t.exit_timestamp = 100.0, datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
    assert pr.rule_already_used([t], pr.RULE_V2.rule_id, "TCS", DAYS[2]) is not None
    assert pr.rule_already_used([t], pr.RULE_V2.rule_id, "TCS", date(2026, 10, 20)) is None
    assert pr.rule_already_used([t], pr.RULE_V1.rule_id, "TCS", DAYS[2]) is None


def test_net_pnl_includes_charges():
    assert pr.net_pnl(1000, 1000, 10) < 0
    assert 0 < pr.net_pnl(1000, 1100, 10) < 1000


def test_rule_stats():
    a, b = trade("A", rule=pr.RULE_V2.rule_id), trade("B", rule=pr.RULE_V2.rule_id)
    a.exit_price, a.realized_pnl = 1100.0, 1000.0
    b.exit_price, b.realized_pnl = 900.0, -500.0
    s = pr.rule_stats(pr.RULE_V2, [a, b, trade("C", rule=pr.RULE_V2.rule_id)])
    assert (s["closed"], s["open"], s["net_pnl"], s["profit_factor"]) == (2, 1, 500.0, 2.0)
