"""Live executor regression tests (all with fake broker and fake database)."""
from datetime import datetime, timedelta

from helpers import IST, LIVE_ON, UTC, FakeBroker, FakeDB, env, trade

import backtest.live_executor as le
from backtest.live_executor import live_book
from brokers.base_broker import OrderStatus

NOW = datetime(2026, 11, 2, 9, 40, tzinfo=IST)


def test_max_five_open_and_no_duplicates():
    trades = [trade(f"S{i}") for i in range(7)] + [trade("TCS", 2000.0, 8)]
    db, b = FakeDB(), FakeBroker()
    with env(**LIVE_ON):
        r = le.execute(db, trades, broker=b, now=NOW)
        assert len(b.orders) == 5 and all(o.quantity == 17 for o in b.orders)
        assert sum("max 5 open" in n for n in r.notes) == 3
        le.execute(db, trades, broker=b, now=NOW + timedelta(minutes=15))
    assert len(b.orders) == 5


def test_entries_only_on_entry_day_before_cutoff():
    db, b = FakeDB(), FakeBroker()
    with env(**LIVE_ON):
        le.execute(db, [trade()], broker=b, now=datetime(2026, 11, 2, 11, 45, tzinfo=IST))   # after 11:30
        le.execute(db, [trade()], broker=b, now=datetime(2026, 11, 3, 9, 40, tzinfo=IST))    # next day
    assert not b.orders


def test_trades_before_live_start_date_ignored():
    db, b = FakeDB(), FakeBroker()
    early = trade(entered=datetime(2026, 10, 30, 3, 45, tzinfo=UTC))
    with env(**LIVE_ON):
        le.execute(db, [early], broker=b, now=datetime(2026, 10, 30, 9, 40, tzinfo=IST))
    assert not b.orders


def test_order_value_cap_reduces_quantity():
    db, b = FakeDB(), FakeBroker()
    with env(**{**LIVE_ON, "LIVE_MAX_ORDER_VALUE": "10000"}):
        le.execute(db, [trade("TCS", 1000.0, 17)], broker=b, now=NOW)
    assert b.orders[0].quantity == 10


def _losers(db):
    out = []
    for i in range(7):
        t = trade(f"L{i}")
        db.add("LIVE_ENTRY", {"trade_id": t.internal_order_id, "order_id": f"x{i}", "qty": 17})
        db.add("LIVE_EXIT", {"trade_id": t.internal_order_id, "order_id": f"y{i}", "qty": 17})
        t.exit_price, t.exit_timestamp, t.realized_pnl = 941.0, datetime(2026, 11, 3, 9, 0, tzinfo=UTC), -1000.0
        out.append(t)
    return out


def test_monthly_limit_blocks_then_resets_next_month():
    db, b = FakeDB(), FakeBroker()
    losers = _losers(db)
    new = trade("NEW", entered=datetime(2026, 11, 4, 3, 45, tzinfo=UTC))
    with env(**LIVE_ON):
        r = le.execute(db, losers + [new], broker=b, now=datetime(2026, 11, 4, 9, 40, tzinfo=IST))
        assert not b.orders and any("monthly loss limit" in n for n in r.notes)
        new2 = trade("NEW2", entered=datetime(2026, 12, 1, 3, 45, tzinfo=UTC))
        le.execute(db, losers + [new2], broker=b, now=datetime(2026, 12, 1, 9, 40, tzinfo=IST))
    assert [o.symbol for o in b.orders] == ["NEW2"]


def test_live_book_rejected_buy_is_not_pnl():
    a, bb, c = trade("A"), trade("B"), trade("C")
    for t in (a, bb):
        t.exit_price, t.exit_timestamp, t.realized_pnl = 950.0, datetime(2026, 11, 5, 10, 0, tzinfo=UTC), -1000.0
    E = {a.internal_order_id: {"qty": 17}, bb.internal_order_id: {"qty": 10}, c.internal_order_id: {"qty": 17}}
    X = {a.internal_order_id: {"qty": 0, "note": "entry REJECTED"}, bb.internal_order_id: {"qty": 10}}
    bk = live_book([a, bb, c], E, X)
    assert bk.open_positions == [("C", 17000.0)]
    assert len(bk.realised) == 1 and abs(bk.realised[0][1] - (-1000 * 10 / 17)) < 1e-6


def _entered(status, filled, gtt=False):
    db, b = FakeDB(), FakeBroker(status=status, filled=filled)
    t = trade("P")
    db.add("LIVE_ENTRY", {"trade_id": t.internal_order_id, "order_id": "e1", "qty": 17})
    if gtt:
        db.add("LIVE_GTT", {"trade_id": t.internal_order_id, "gtt_id": "g1", "qty": 17})
    return db, b, t


def test_pending_buy_cancelled_on_exit_and_no_fake_pnl():
    for status, expect_cancel in ((OrderStatus.PENDING, True), (OrderStatus.REJECTED, False)):
        db, b, t = _entered(status, 0)
        t.exit_price, t.exit_timestamp, t.realized_pnl = 1100.0, datetime(2026, 11, 2, 9, 0, tzinfo=UTC), 1700.0
        with env(**LIVE_ON):
            le.execute(db, [t], broker=b, now=datetime(2026, 11, 3, 9, 40, tzinfo=IST))
        ex = db.of("LIVE_EXIT")[0]
        assert ex["qty"] == 0 and ex["note"].startswith("entry")
        assert (b.cancelled == ["e1"]) == expect_cancel and not b.orders
        assert live_book([t], {t.internal_order_id: {"qty": 17}}, {t.internal_order_id: ex}).realised == []


def test_filled_buy_gets_gtt_stop_once():
    db, b, t = _entered(OrderStatus.FILLED, 17)
    with env(**LIVE_ON):
        le.execute(db, [t], broker=b, now=datetime(2026, 11, 2, 10, 0, tzinfo=IST))
        le.execute(db, [t], broker=b, now=datetime(2026, 11, 2, 11, 0, tzinfo=IST))
    assert b.gtts == [("P", 17, t.stop_price)]


def test_rejected_buy_recorded_without_position():
    db, b, t = _entered(OrderStatus.REJECTED, 0)
    with env(**LIVE_ON):
        r = le.execute(db, [t], broker=b, now=datetime(2026, 11, 2, 10, 0, tzinfo=IST))
    assert db.of("LIVE_EXIT")[0]["note"].startswith("entry") and r.errors and not b.gtts


def test_gtt_sold_already_means_real_pnl_counts():
    db, b, t = _entered(OrderStatus.FILLED, 17, gtt=True)
    t.exit_price, t.exit_timestamp, t.realized_pnl = 950.0, datetime(2026, 11, 2, 9, 0, tzinfo=UTC), -1000.0
    with env(**LIVE_ON):
        le.execute(db, [t], broker=b, now=datetime(2026, 11, 3, 9, 40, tzinfo=IST))
    ex = db.of("LIVE_EXIT")[0]
    assert "note" not in ex and ex["qty"] == 0 and b.gtt_cancelled == ["g1"]
    assert len(live_book([t], {t.internal_order_id: {"qty": 17}}, {t.internal_order_id: ex}).realised) == 1


def test_exit_sells_only_what_is_held():
    db, b, t = _entered(OrderStatus.FILLED, 17, gtt=True)
    b.holdings = {"P": 40}            # more than this trade bought: never sell other holdings
    t.exit_price, t.exit_timestamp, t.realized_pnl = 1050.0, datetime(2026, 11, 2, 9, 0, tzinfo=UTC), 800.0
    with env(**LIVE_ON):
        le.execute(db, [t], broker=b, now=datetime(2026, 11, 3, 9, 40, tzinfo=IST))
    assert [o.quantity for o in b.orders] == [17]
