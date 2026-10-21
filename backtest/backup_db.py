"""Weekly backup of the whole Garud database (trades + every audit event) to a compressed
JSON file kept as a GitHub Actions artifact for 90 days. Read-only: never writes to the
database, never sends secrets. Restore = download the artifact (it is plain JSON)."""
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _row(obj, cols) -> dict:
    out = {}
    for c in cols:
        v = getattr(obj, c)
        out[c] = v.isoformat() if hasattr(v, "isoformat") else v
    return out


def dump(session, trade_cls, event_cls) -> dict:
    tcols = [c.name for c in trade_cls.__table__.columns]
    ecols = [c.name for c in event_cls.__table__.columns]
    trades = [_row(t, tcols) for t in session.query(trade_cls).all()]
    events = [_row(e, ecols) for e in session.query(event_cls).order_by(event_cls.id).all()]
    kinds = {}
    for e in events:
        kinds[e["event_type"]] = kinds.get(e["event_type"], 0) + 1
    return {"created": datetime.now(timezone.utc).isoformat(), "trades": trades, "audit_events": events,
            "counts": {"trades": len(trades), "audit_events": len(events), "by_type": kinds}}


def write(backup: dict, path: str) -> int:
    data = json.dumps(backup, default=str).encode()
    with gzip.open(path, "wb") as f:
        f.write(data)
    return os.path.getsize(path)


def main() -> int:
    from config.settings import load_settings
    from database.db import AuditEventORM, Database, TradeRecordORM
    from backtest.run_rule_paper import send_telegram
    settings = load_settings()
    if settings.database_url.startswith("sqlite"):
        print("DATABASE_URL is not the hosted database — nothing to back up.")
        return 1
    db = Database(settings)
    db.connect()
    session = db._session()
    try:
        backup = dump(session, TradeRecordORM, AuditEventORM)
    finally:
        session.close()
    name = f"garud_backup_{datetime.now(timezone.utc):%Y%m%d}.json.gz"
    size = write(backup, name)
    c = backup["counts"]
    text = (f"💾 Garud weekly backup: {c['trades']} trades, {c['audit_events']} events, {size / 1024:.0f} KB "
            "— saved for 90 days under Actions → 'Database backup (weekly)' → Artifacts")
    print(text)
    print(json.dumps(c["by_type"], indent=1))
    send_telegram(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
