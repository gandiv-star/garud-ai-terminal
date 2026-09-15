from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AuditRecord:
    timestamp: datetime
    symbol: str
    decision: str
    reason: str
    details: dict = field(default_factory=dict)


class AuditTrail:
    def __init__(self, database):
        self.database = database

    def record(self, symbol: str, decision: str, reason: str, **details) -> None:
        record = AuditRecord(
            timestamp=datetime.now(timezone.utc),
            symbol=symbol,
            decision=decision,
            reason=reason,
            details=details,
        )
        self.database.save_audit_event(record)
