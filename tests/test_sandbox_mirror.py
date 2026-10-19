"""Sandbox mirror: which orders every paper trade implies (rule trades only)."""
from helpers import trade

from backtest import sandbox_mirror as sm


def test_expected_orders_entry_and_exit():
    a = trade("A")
    b = trade("B")
    b.exit_price = 1050.0
    c = trade("C")
    manual = trade("M", rule="composite")
    out = sm.expected_orders([a, b, c, manual], due_exits={c.internal_order_id})
    ids = [o["internal_order_id"] for o in out]
    assert ids == [f"{a.internal_order_id}:ENTRY", f"{b.internal_order_id}:ENTRY", f"{b.internal_order_id}:EXIT",
                   f"{c.internal_order_id}:ENTRY", f"{c.internal_order_id}:EXIT"]
    assert {o["side"] for o in out if o["internal_order_id"].endswith(":EXIT")} == {"SELL"}
    assert all(o["quantity"] == 17 for o in out)


def test_manual_tools_trades_never_mirrored():
    assert sm.expected_orders([trade("M", rule="composite")]) == []


class _Broker:
    token = "dummy"
    after_hours = False

    def place_order(self, req):
        raise AssertionError("no order expected in this test")


def test_presold_time_exit_is_not_reported_as_unknown():
    """15:20 run sends the time-exit SELL; the paper trade closes only in the evening run.
    A 15:32 run in between must not raise 'unknown sandbox order'."""
    from datetime import datetime
    from helpers import IST, FakeDB
    t = trade("DLF", rule="volatility_expansion_rule_v1")
    db = FakeDB()
    for side, sfx in (("BUY", "ENTRY"), ("SELL", "EXIT")):
        db.add(sm.EVENT_OK, {"internal_order_id": f"{t.internal_order_id}:{sfx}", "symbol": "DLF",
                             "side": side, "quantity": t.quantity, "broker_order_id": "x"})
    r = sm.mirror(db, [t], broker=_Broker(), now=datetime(2026, 10, 19, 15, 32, tzinfo=IST))
    assert r.unreconciled == [], r.unreconciled


def test_really_unknown_order_still_reported():
    from datetime import datetime
    from helpers import IST, FakeDB
    db = FakeDB()
    db.add(sm.EVENT_OK, {"internal_order_id": "volatility_expansion_rule_v1-XYZ-1:EXIT", "symbol": "XYZ",
                         "side": "SELL", "quantity": 5, "broker_order_id": "x"})
    r = sm.mirror(db, [], broker=_Broker(), now=datetime(2026, 10, 19, 15, 32, tzinfo=IST))
    assert any("unknown sandbox order" in u for u in r.unreconciled)
