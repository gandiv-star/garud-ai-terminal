import uuid
from dataclasses import dataclass

from brokers.base_broker import BaseBroker, OrderRequest, OrderResult


@dataclass
class OrderManager:
    broker: BaseBroker

    def new_internal_id(self) -> str:
        return f"garud-{uuid.uuid4()}"

    def submit(self, order: OrderRequest) -> OrderResult:
        if not order.internal_order_id:
            raise ValueError("OrderRequest must carry an internal_order_id before submission")
        # TODO: de-dup check against recently submitted internal_order_ids
        # before calling the broker.
        return self.broker.place_order(order)
