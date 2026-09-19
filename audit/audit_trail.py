from datetime import datetime, timezone

from database.models import AuditEvent


class AuditTrail:
    def __init__(self, database):
        self.database = database

    def record(self, symbol: str, event_type: str, **details) -> None:
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            symbol=symbol,
            payload=details,
        )
        self.database.save_audit_event(event)
