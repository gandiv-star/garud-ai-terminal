"""
Order/Position Reconciliation.

Continuously compares internal system state against broker state. Any
mismatch must be FLAGGED, never silently resolved by placing another
order.
"""

from dataclasses import dataclass, field

FIELDS_TO_COMPARE = ("status", "quantity", "price", "side")


@dataclass
class ReconciliationMismatch:
    internal_order_id: str
    field: str
    internal_value: str
    broker_value: str


@dataclass
class ReconciliationReport:
    mismatches: list[ReconciliationMismatch] = field(default_factory=list)
    missing_from_broker: list[str] = field(default_factory=list)
    missing_from_internal: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.mismatches and not self.missing_from_broker and not self.missing_from_internal


class ReconciliationEngine:
    def reconcile(self, internal_orders: list[dict], broker_orders: list[dict]) -> ReconciliationReport:
        """
        Both lists are dicts keyed at minimum by 'internal_order_id', plus
        whatever fields in FIELDS_TO_COMPARE each side has. Never raises on
        a mismatch — it reports it, so the caller (a human, or a future
        alerting layer) decides what to do. Reconciliation never places or
        cancels an order itself.
        """
        report = ReconciliationReport()

        internal_by_id = {o["internal_order_id"]: o for o in internal_orders}
        broker_by_id = {o["internal_order_id"]: o for o in broker_orders}

        for internal_id, internal_order in internal_by_id.items():
            broker_order = broker_by_id.get(internal_id)
            if broker_order is None:
                report.missing_from_broker.append(internal_id)
                continue
            for field_name in FIELDS_TO_COMPARE:
                internal_value = internal_order.get(field_name)
                broker_value = broker_order.get(field_name)
                if internal_value is not None and broker_value is not None and internal_value != broker_value:
                    report.mismatches.append(
                        ReconciliationMismatch(
                            internal_order_id=internal_id,
                            field=field_name,
                            internal_value=str(internal_value),
                            broker_value=str(broker_value),
                        )
                    )

        for broker_id in broker_by_id:
            if broker_id not in internal_by_id:
                report.missing_from_internal.append(broker_id)

        return report
