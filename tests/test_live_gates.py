"""A2 — live orders must FAIL CLOSED: missing or invalid configuration never sends a BUY.
Exits are never blocked by a bad setting."""
import json
import os
from datetime import datetime

import pytest

from helpers import IST, LIVE_ON, ROOT_FILE, FakeBroker, FakeDB, env, trade

import backtest.live_executor as le
from backtest import live_guard
from brokers import upstox_live
from brokers.base_broker import OrderRequest, OrderSide, OrderStatus

NOW = datetime(2026, 11, 2, 9, 40, tzinfo=IST)


def _run(trades=None, broker=None, now=NOW, db=None):
    db, broker = db or FakeDB(), broker or FakeBroker()
    r = le.execute(db, trades or [trade()], broker=broker, now=now)
    return r, broker, db


# ---------------------------------------------------------------- the four gates
def test_nothing_set_means_live_off_and_no_broker_call():
    r, b, db = _run()
    assert not b.orders and not db.ev
    assert r.notes[0].startswith("Live trading OFF")


@pytest.mark.parametrize("changes", [
    {"TRADING_MODE": None}, {"TRADING_MODE": "PAPER"}, {"TRADING_MODE": "live-ish"},
    {"LIVE_ORDERS_ENABLED": None}, {"LIVE_ORDERS_ENABLED": "NO"}, {"LIVE_ORDERS_ENABLED": "true"},
    {"LIVE_ORDERS_ENABLED": ""},
    {"LIVE_RULES": None}, {"LIVE_RULES": ""}, {"LIVE_RULES": "made_up_rule"},
    {"LIVE_START_DATE": None}, {"LIVE_START_DATE": ""}, {"LIVE_START_DATE": "2026-13-01"},
    {"LIVE_START_DATE": "next monday"},
])
def test_any_closed_gate_blocks_everything(changes):
    with env(**{**LIVE_ON, **changes}):
        r, b, db = _run()
    assert not b.orders and not db.ev, changes
    assert r.notes and r.notes[0].startswith("Live trading OFF"), changes


def test_all_gates_open_sends_one_buy_sanity_check():
    with env(**LIVE_ON):
        r, b, db = _run()
    assert [(o.symbol, o.side, o.quantity) for o in b.orders] == [("TCS", OrderSide.BUY, 17)]
    assert db.of("LIVE_ENTRY")[0]["qty"] == 17


def test_kill_switch_blocks_new_buys():
    with env(**LIVE_ON):
        db, b = FakeDB(), FakeBroker()
        le.execute(db, [trade()], broker=b, now=NOW, allow_entries=False)
    assert not b.orders


# ---------------------------------------------------------------- limit variables (A2)
BAD_VALUES = ("abc", "50,000", "inf", "-inf", "nan", "1e999", "-5")


@pytest.mark.parametrize("name", sorted(live_guard.LIMITS))
@pytest.mark.parametrize("value", BAD_VALUES)
def test_invalid_limit_blocks_new_buys(name, value):
    with env(**{**LIVE_ON, name: value}):
        r, b, db = _run()
        status = le.effective_status()
    assert not b.orders, (name, value, r.notes)
    assert any("blocked until fixed" in n and name in n for n in r.notes), r.notes
    assert any(name in p for p in status["problems"])


@pytest.mark.parametrize("name", sorted(live_guard.LIMITS))
def test_empty_limit_uses_safe_default(name):
    """An unset GitHub variable arrives as an empty string: that is 'use the default', not an error."""
    with env(**{**LIVE_ON, name: ""}):
        r, b, _ = _run()
        assert live_guard.config_problems() == []
    assert len(b.orders) == 1, r.notes


def test_all_limit_vars_empty_like_the_workflow_passes_them():
    blanks = {n: "" for n in live_guard.LIMITS}
    with env(**{**LIVE_ON, **blanks}):
        cfg = live_guard.GuardConfig.from_env()
        assert cfg == live_guard.GuardConfig()
        assert upstox_live.max_order_value() == upstox_live.DEFAULT_MAX_ORDER_VALUE
        r, b, _ = _run()
    assert len(b.orders) == 1


def test_valid_limits_are_used():
    with env(**{**LIVE_ON, "LIVE_CAPITAL": "50000", "LIVE_MAX_OPEN": "3", "LIVE_MAX_STOCK_PCT": "10",
                "LIVE_DAILY_LOSS_LIMIT": "0", "LIVE_MONTHLY_LOSS_LIMIT": "3000", "LIVE_MAX_ORDER_VALUE": "30000"}):
        assert live_guard.config_problems() == []
        cfg = live_guard.GuardConfig.from_env()
        assert (cfg.capital, cfg.max_open, cfg.max_stock_pct, cfg.daily_loss_limit, cfg.monthly_loss_limit) == \
            (50000, 3, 10, 0, 3000)
        assert upstox_live.max_order_value() == 30000
        r, b, _ = _run()
    assert b.orders[0].quantity == 5          # 10% of 50,000 = 5,000 -> 5 shares at 1,000


def test_monthly_limit_cannot_be_switched_off_with_zero():
    with env(**{**LIVE_ON, "LIVE_MONTHLY_LOSS_LIMIT": "0"}):
        r, b, _ = _run()
    assert not b.orders and any("LIVE_MONTHLY_LOSS_LIMIT" in n for n in r.notes)


def test_daily_limit_zero_means_off_and_is_valid():
    with env(**{**LIVE_ON, "LIVE_DAILY_LOSS_LIMIT": "0"}):
        assert live_guard.config_problems() == []


def test_max_open_must_be_whole():
    with env(LIVE_MAX_OPEN="2.5"):
        assert live_guard.config_problems()


def test_bad_limit_never_stops_an_exit():
    """A trade already bought live must still be sold even while a setting is broken."""
    t = trade()
    db = FakeDB()
    db.add("LIVE_ENTRY", {"trade_id": t.internal_order_id, "order_id": "e1", "qty": 17})
    db.add("LIVE_GTT", {"trade_id": t.internal_order_id, "gtt_id": "g1", "qty": 17})
    t.exit_price, t.exit_timestamp, t.realized_pnl = 950.0, datetime(2026, 11, 3, 4, 0, tzinfo=IST), -900.0
    b = FakeBroker(status=OrderStatus.FILLED, filled=17, holdings={"TCS": 17})
    with env(**{**LIVE_ON, "LIVE_CAPITAL": "abc"}):
        le.execute(db, [t], broker=b, now=datetime(2026, 11, 3, 9, 40, tzinfo=IST))
    sells = [o for o in b.orders if o.side == OrderSide.SELL]
    assert len(sells) == 1 and sells[0].quantity == 17 and b.gtt_cancelled == ["g1"]


# ---------------------------------------------------------------- per-order cap at the broker
@pytest.mark.parametrize("value", ["inf", "nan", "abc", "-1", "0", "1e12"])
def test_invalid_order_cap_refuses_every_buy_inside_the_broker(value):
    with env(**{**LIVE_ON, "LIVE_MAX_ORDER_VALUE": value}):
        assert upstox_live.max_order_value() == 0.0
        assert upstox_live.max_order_value_problem()
        broker = upstox_live.UpstoxLiveBroker(token="dummy-not-a-real-token")
        with pytest.raises(upstox_live.LiveOrdersDisabled):
            broker.place_order(OrderRequest("t:LIVE_ENTRY", "TCS", "NSE", OrderSide.BUY, 1, "MARKET",
                                            price=1000.0, product_type="D"))


def test_closed_gate_raises_before_any_network_call():
    broker = upstox_live.UpstoxLiveBroker(token="dummy-not-a-real-token")
    with env(TRADING_MODE="PAPER", LIVE_ORDERS_ENABLED="YES"):
        with pytest.raises(upstox_live.LiveOrdersDisabled):
            broker.place_order(OrderRequest("t:LIVE_ENTRY", "TCS", "NSE", OrderSide.BUY, 1, "MARKET",
                                            price=1000.0, product_type="D"))
        with pytest.raises(upstox_live.LiveOrdersDisabled):
            broker.place_gtt_stop("TCS", 1, 900.0)
        with pytest.raises(upstox_live.LiveOrdersDisabled):
            broker.cancel_order("x")


def test_order_above_cap_refused():
    with env(**LIVE_ON):
        broker = upstox_live.UpstoxLiveBroker(token="dummy-not-a-real-token")
        with pytest.raises(upstox_live.LiveOrdersDisabled):
            broker.place_order(OrderRequest("t", "TCS", "NSE", OrderSide.BUY, 30, "MARKET", price=1000.0))


# ---------------------------------------------------------------- reporting & workflow wiring
def test_status_never_contains_secrets():
    with env(**{**LIVE_ON, "BROKER_ACCESS_TOKEN": "SECRET-TOKEN-123", "UPSTOX_SANDBOX_TOKEN": "SECRET-2"}):
        text = json.dumps(le.effective_status())
    assert "SECRET" not in text


def test_status_reports_off_by_default():
    s = le.effective_status()
    assert s["active"] is False and s["orders_allowed"] is False and s["problems"] == []
    assert s["guard"] == live_guard.GuardConfig().as_dict()


def test_workflow_passes_every_live_variable_to_the_run_step():
    wf = open(ROOT_FILE(".github/workflows/rule_paper_trading.yml"), encoding="utf-8").read()
    step = wf.split("- name: Run rules", 1)[1].split("- name:", 1)[0]
    for name in ("LIVE_ORDERS_ENABLED", "LIVE_RULES", "LIVE_START_DATE", *live_guard.LIMITS):
        assert f"{name}: ${{{{ vars.{name} }}}}" in step, name
    assert "TRADING_MODE: ${{ vars.TRADING_MODE || 'PAPER' }}" in step


def test_options_step_is_always_paper():
    wf = open(ROOT_FILE(".github/workflows/rule_paper_trading.yml"), encoding="utf-8").read()
    step = wf.split("- name: Run options paper", 1)[1].split("- name:", 1)[0]
    assert "TRADING_MODE: PAPER" in step and "LIVE_" not in step
