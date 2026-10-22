"""Live execution safety (#25 order states, #26 reconciliation, #47/#118 cash, #113 partial fills,
#115 unknown state, #117 tick size / quantity). Fake broker and fake database only — no orders."""
from datetime import date, datetime

import pytest

from helpers import IST, LIVE_ON, FakeBroker, FakeDB, env, trade

import backtest.live_executor as le
from brokers.base_broker import OrderStatus
from execution import order_state as osm
from execution import position_recon as pr
from risk import pretrade as pt

NOW = datetime(2026, 11, 2, 9, 40, tzinfo=IST)
LATER = datetime(2026, 11, 2, 10, 0, tzinfo=IST)
NEXT_DAY = datetime(2026, 11, 3, 9, 40, tzinfo=IST)


# ---------------------------------------------------------------- tick size / quantity / cash
def test_tick_bands_2025():
    assert [pt.tick_size(p) for p in (100, 250, 251, 1000, 1001, 5000, 5001, 10001, 20001)] == \
        [0.01, 0.01, 0.05, 0.05, 0.10, 0.10, 0.50, 1.00, 5.00]


def test_round_to_tick_for_stops():
    assert pt.round_to_tick(976.63, "up") == 976.65
    assert pt.round_to_tick(976.63, "down") == 976.6
    assert pt.round_to_tick(6728.53, "up") == 6729.0             # 5,000–10,000 band: 0.50
    assert pt.round_to_tick(1490.04, "up") == 1490.1
    assert pt.round_to_tick(248.0, "up") == 248.0                 # within 2% of 250: 0.05 grid (valid in both)
    assert pt.round_to_tick(950.0, "up") == 950.0
    for p in (976.63, 6728.53, 248.01, 4950.07, 19876.3):
        r = pt.round_to_tick(p, "up")
        assert r >= p and pt.on_tick(r)
    with pytest.raises(ValueError):
        pt.round_to_tick(0)


def test_quantity_problems():
    assert pt.quantity_problem(5) is None
    for bad in (0, -3, 1.5, True, "3"):
        assert pt.quantity_problem(bad)


def test_available_margin_parsing_fails_closed():
    assert pt.available_margin({"data": {"equity": {"available_margin": 52000.5}}}) == 52000.5
    for bad in ({}, {"data": {}}, {"data": {"equity": {"available_margin": "x"}}}, None,
                {"data": {"equity": {"available_margin": -5}}}, {"data": {"equity": {"available_margin": float("nan")}}}):
        assert pt.available_margin(bad) is None


def test_affordable_qty():
    ch = lambda v: v * 0.002                                       # noqa: E731
    assert pt.affordable_qty(10, 1000, None, ch)[0] == 0           # unknown cash -> blocked
    assert pt.affordable_qty(10, 1000, 100000, ch) == (10, "")
    q, why = pt.affordable_qty(10, 1000, 5200, ch)
    assert q == 5 and "reduced" in why                             # 5*1000*1.01 + 10 = 5060 <= 5200
    assert pt.affordable_qty(10, 1000, 900, ch)[0] == 0


# ---------------------------------------------------------------- order state machine
def test_transitions():
    assert osm.legal(None, "OPEN") and osm.legal("OPEN", "PARTIALLY_FILLED") and osm.legal("OPEN", "OPEN")
    assert osm.legal("PARTIALLY_FILLED", "CANCELLED") and osm.legal("UNKNOWN", "FILLED")
    assert not osm.legal("FILLED", "OPEN") and not osm.legal("CANCELLED", "FILLED")
    assert not osm.legal("PARTIALLY_FILLED", "PENDING")


def test_entry_actions():
    d0, d1 = date(2026, 11, 2), date(2026, 11, 3)
    assert osm.entry_action("FILLED", 17, d0, d0) == ("protect", 17)
    assert osm.entry_action("CANCELLED", 5, d0, d0) == ("protect", 5)       # partial, then cancelled
    assert osm.entry_action("REJECTED", 0, d0, d0) == ("none", 0)
    assert osm.entry_action("OPEN", 0, d0, d0) == ("wait", 0)
    assert osm.entry_action("PARTIALLY_FILLED", 5, d0, d1) == ("cancel_and_protect", 5)
    assert osm.entry_action("PENDING", 0, d0, d1) == ("cancel_and_protect", 0)
    assert osm.entry_action("UNKNOWN", 0, d0, d1) == ("wait", 0)
    assert osm.last_states([{"order_id": "a", "state": "OPEN", "seq": 1},
                            {"order_id": "a", "state": "FILLED", "seq": 2}]) == {"a": "FILLED"}


# ---------------------------------------------------------------- reconciliation
def test_reconcile():
    entries = {"t1": {"symbol": "A", "qty": 10}, "t2": {"symbol": "B", "qty": 8}, "t3": {"symbol": "C", "qty": 5}}
    gtts = {"t1": {"qty": 10}}
    exits = {"t3": {"qty": 5}}
    exp = pr.expected(entries, gtts, exits)
    assert exp == {"A": (10, 10), "B": (0, 8)}
    assert pr.reconcile(exp, {"A": 10, "B": 3}) == []
    probs = pr.reconcile(exp, {"A": 4, "B": 9, "C": 50})
    assert any("A: broker holds 4" in p and "missing" in p for p in probs)
    assert any("B: broker holds 9" in p and "extra" in p for p in probs)
    assert not any(p.startswith("C") for p in probs)               # closed / not Garud's: ignored


# ---------------------------------------------------------------- executor integration
def _entered(status, filled, symbol="P", stop=None):
    db, b = FakeDB(), FakeBroker(status=status, filled=filled)
    t = trade(symbol, stop=stop)
    db.add("LIVE_ENTRY", {"trade_id": t.internal_order_id, "symbol": symbol, "order_id": "e1", "qty": 17})
    return db, b, t


def test_funds_unreadable_blocks_buy_and_low_cash_reduces():
    db, b = FakeDB(), FakeBroker(funds=RuntimeError("down"))
    with env(**LIVE_ON):
        r = le.execute(db, [trade()], broker=b, now=NOW)
    assert not b.orders and any("funds unreadable" in n for n in r.notes)
    db, b = FakeDB(), FakeBroker(funds=8000.0)
    with env(**LIVE_ON):
        r = le.execute(db, [trade("TCS", 1000.0, 17)], broker=b, now=NOW)
    assert b.orders and b.orders[0].quantity == 7 and any("reduced" in n for n in r.notes)


def test_cash_is_used_up_across_buys_in_one_run():
    db, b = FakeDB(), FakeBroker(funds=20000.0)
    with env(**LIVE_ON):
        le.execute(db, [trade("A", 1000.0, 10), trade("B", 1000.0, 10), trade("C", 1000.0, 10)], broker=b, now=NOW)
    assert sum(o.quantity * 1000 for o in b.orders) <= 20000 and len(b.orders) == 2


def test_partial_fill_then_cancelled_gets_stop_for_filled_qty():
    db, b, t = _entered(OrderStatus.CANCELLED, 5, stop=976.63)
    with env(**LIVE_ON):
        r = le.execute(db, [t], broker=b, now=LATER)
    assert b.gtts == [("P", 5, 976.65)] and any("partial fill 5/17" in a for a in r.actions)
    assert not db.of("LIVE_EXIT")


def test_order_still_working_next_day_is_cancelled_then_protected():
    db, b, t = _entered(OrderStatus.PARTIALLY_FILLED, 6)
    with env(**LIVE_ON):
        le.execute(db, [t], broker=b, now=NEXT_DAY)
    assert b.cancelled == ["e1"] and b.gtts == [("P", 6, 950.0)]
    db, b, t = _entered(OrderStatus.OPEN, 0)
    with env(**LIVE_ON):
        le.execute(db, [t], broker=b, now=NEXT_DAY)
    assert b.cancelled == ["e1"] and not b.gtts and db.of("LIVE_EXIT")[0]["note"] == "entry OPEN"


def test_same_day_working_order_waits():
    db, b, t = _entered(OrderStatus.OPEN, 0)
    with env(**LIVE_ON):
        le.execute(db, [t], broker=b, now=LATER)
    assert not b.cancelled and not b.gtts and not db.of("LIVE_EXIT")


def test_unknown_status_recorded_and_retried():
    db, b, t = _entered(OrderStatus.FILLED, 17)

    def boom(order_id):
        raise TimeoutError("no answer")
    b.get_order_status = boom
    with env(**LIVE_ON):
        r = le.execute(db, [t], broker=b, now=LATER)
    assert not b.gtts and any("status unknown" in n for n in r.notes)
    assert [p["state"] for p in db.of("LIVE_ORDER_STATE")] == ["UNKNOWN"]
    del b.get_order_status                                          # broker answers again
    with env(**LIVE_ON):
        le.execute(db, [t], broker=b, now=LATER)
    assert b.gtts == [("P", 17, 950.0)]
    assert sorted(p["state"] for p in db.of("LIVE_ORDER_STATE")) == ["FILLED", "UNKNOWN"]


def test_state_stored_once_per_change():
    db, b, t = _entered(OrderStatus.OPEN, 0)
    with env(**LIVE_ON):
        le.execute(db, [t], broker=b, now=LATER)
        le.execute(db, [t], broker=b, now=LATER)
    assert [p["state"] for p in db.of("LIVE_ORDER_STATE")] == ["OPEN"]


def test_reconciliation_flags_missing_shares():
    db, b, t = _entered(OrderStatus.FILLED, 17)
    db.add("LIVE_GTT", {"trade_id": t.internal_order_id, "gtt_id": "g1", "qty": 17})
    b.holdings = {"P": 0}
    with env(**LIVE_ON):
        r = le.execute(db, [t], broker=b, now=LATER)
    assert any("P: broker holds 0" in e for e in r.errors)
    assert db.of("LIVE_RECON")[0]["problems"]
    b.holdings = {"P": 17}
    with env(**LIVE_ON):
        r = le.execute(db, [t], broker=b, now=LATER)
    assert not any("broker holds" in e for e in r.errors)


def test_reconciliation_read_failure_is_reported_not_fatal():
    db, b, t = _entered(OrderStatus.FILLED, 17)

    def down():
        raise ConnectionError("x")
    b.get_positions = down
    with env(**LIVE_ON):
        r = le.execute(db, [t], broker=b, now=LATER)
    assert b.gtts and any("reconciliation skipped" in n for n in r.notes)
