from dataclasses import dataclass, field


@dataclass
class ReconciliationMismatch:
    internal_order_id: str
    field: str
    internal_value: str
    broker_value: str


@dataclass
class ReconciliationReport:
    mismatches: list[ReconciliationMismatch] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.mismatches) == 0


class ReconciliationEngine:
    def reconcile(self, internal_orders: list[dict], broker_orders: list[dict]) -> ReconciliationReport:
        raise NotImplementedError
