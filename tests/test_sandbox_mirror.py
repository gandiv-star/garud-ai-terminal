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
