"""
Order Manager.

Guards against duplicate orders, stale signals/prices, and wrong
quantity/symbol/exchange/product/direction. Every order gets an internal
unique identifier BEFORE it reaches the broker — that ID is what
reconciliation.py matches against broker state afterward.

Duplicate protection has two layers:
1. Exact internal_order_id re-submission (e.g. a retried request) is
   always rejected — an ID is used exactly once.
2. A same-symbol/side/quantity submission within `dedup_window_seconds`
   of a prior one is rejected too, to catch accidental double-clicks or
   a retried UI action that generated a fresh internal_order_id.
"""

import time
from dataclasses import dataclass, field

from brokers.base_broker import BaseBroker, OrderRequest, OrderResult


class DuplicateOrderError(Exception):
    pass


@dataclass
class OrderManager:
    broker: BaseBroker
    dedup_window_seconds: float = 5.0
    _seen_ids: set[str] = field(default_factory=set)
    _recent_signatures: dict[tuple, float] = field(default_factory=dict)

    def new_internal_id(self) -> str:
        import uuid

        return f"garud-{uuid.uuid4()}"

    def _signature(self, order: OrderRequest) -> tuple:
        return (order.symbol, order.side, order.quantity, order.exchange)

    def submit(self, order: OrderRequest) -> OrderResult:
        if not order.internal_order_id:
            raise ValueError("OrderRequest must carry an internal_order_id before submission")

        if order.internal_order_id in self._seen_ids:
            raise DuplicateOrderError(
                f"internal_order_id {order.internal_order_id} has already been submitted"
            )

        now = time.time()
        sig = self._signature(order)
        last_seen = self._recent_signatures.get(sig)
        if last_seen is not None and (now - last_seen) < self.dedup_window_seconds:
            raise DuplicateOrderError(
                f"Same order ({order.symbol} {order.side.value} x{order.quantity}) "
                f"was submitted {now - last_seen:.1f}s ago — within the "
                f"{self.dedup_window_seconds}s de-dup window."
            )

        self._seen_ids.add(order.internal_order_id)
        self._recent_signatures[sig] = now
        return self.broker.place_order(order)
