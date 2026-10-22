"""Order state machine for LIVE orders (#25), partial fills (#113) and unknown/stale orders (#115).

States follow the broker statuses (brokers.base_broker.OrderStatus) plus UNKNOWN when the
broker cannot be asked. Every change is stored once as a LIVE_ORDER_STATE audit event, so the
history of each order can be rebuilt. Only the live path uses this (live trading is OFF).
"""
from brokers.base_broker import OrderStatus

UNKNOWN = "UNKNOWN"
TERMINAL = {OrderStatus.FILLED.value, OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value}
ALLOWED = {
    None: {OrderStatus.PENDING.value, OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value,
           OrderStatus.FILLED.value, OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value, UNKNOWN},
    OrderStatus.PENDING.value: {OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value, OrderStatus.FILLED.value,
                                OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value, UNKNOWN},
    OrderStatus.OPEN.value: {OrderStatus.PARTIALLY_FILLED.value, OrderStatus.FILLED.value,
                             OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value, UNKNOWN},
    OrderStatus.PARTIALLY_FILLED.value: {OrderStatus.FILLED.value, OrderStatus.CANCELLED.value, UNKNOWN},
    UNKNOWN: {OrderStatus.PENDING.value, OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value,
              OrderStatus.FILLED.value, OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value, UNKNOWN},
    OrderStatus.FILLED.value: set(),
    OrderStatus.CANCELLED.value: set(),
    OrderStatus.REJECTED.value: set(),
}


def legal(prev: str | None, new: str) -> bool:
    return prev == new or new in ALLOWED.get(prev, set())


def entry_action(status: str, filled: int, entry_day, today) -> tuple[str, int]:
    """What to do with a live BUY. Returns (action, qty):
      'protect'            -> place the stop for `qty` filled shares (FILLED, or partly filled then
                              cancelled/rejected: the shares bought still need a stop)
      'cancel_and_protect' -> the order is still working on a later day (a market BUY must not linger):
                              cancel it, then protect whatever filled (qty may be 0)
      'none'               -> nothing was bought (cancelled/rejected with 0 filled)
      'wait'               -> still working today; check again next run
    """
    filled = int(filled or 0)
    if status == OrderStatus.FILLED.value:
        return ("protect", filled) if filled > 0 else ("wait", 0)
    if status in (OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value):
        return ("protect", filled) if filled > 0 else ("none", 0)
    if status in (OrderStatus.PENDING.value, OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value):
        return ("cancel_and_protect", filled) if today > entry_day else ("wait", 0)
    return "wait", 0          # UNKNOWN or anything new: never act on a guess


def last_states(events: list) -> dict:
    """{order_id: last stored state} from LIVE_ORDER_STATE payloads (newest first or any order)."""
    out = {}
    for p in sorted(events, key=lambda p: p.get("seq", 0)):
        if p.get("order_id"):
            out[p["order_id"]] = p.get("state")
    return out
