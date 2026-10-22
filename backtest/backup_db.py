"""Weekly backup of the whole Garud database (trades + every audit event) to a compressed
JSON file kept as a GitHub Actions artifact for 90 days. Read-only: never writes to the
database, never sends secrets. Restore = download the artifact (it is plain JSON).

Restore drill (every run): the file just written is read back and loaded into a throw-away
SQLite database (Python's built-in sqlite3, independent of the app's database code); row counts
per table and per event type, unique ids and the total realised P&L must match the live
database dump exactly, otherwise the run fails and Telegram says so."""
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


def restore_drill(path: str) -> dict:
    """Loads the backup file into an in-memory SQLite database and re-reads it.
    Returns {"ok": bool, "problems": [...], "trades": n, "audit_events": n}."""
    import sqlite3
    with gzip.open(path, "rb") as f:
        b = json.loads(f.read())
    con = sqlite3.connect(":memory:")
    problems = []
    for table, rows in (("trades", b.get("trades") or []), ("audit_events", b.get("audit_events") or [])):
        cols = sorted({k for r in rows for k in r}) or ["_empty"]
        con.execute(f'CREATE TABLE {table} ({", ".join(f"[{c}]" for c in cols)})')
        con.executemany(f'INSERT INTO {table} VALUES ({", ".join("?" for _ in cols)})',
                        [[json.dumps(r.get(c)) if isinstance(r.get(c), (dict, list)) else r.get(c) for c in cols]
                         for r in rows])
    counts = b.get("counts") or {}
    n_t = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    n_e = con.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    if n_t != counts.get("trades"):
        problems.append(f"trades {n_t} != {counts.get('trades')}")
    if n_e != counts.get("audit_events"):
        problems.append(f"audit_events {n_e} != {counts.get('audit_events')}")
    if n_t:
        uniq = con.execute("SELECT COUNT(DISTINCT internal_order_id) FROM trades").fetchone()[0]
        if uniq != n_t:
            problems.append(f"duplicate trade ids: {n_t - uniq}")
        pnl_db = round(con.execute("SELECT COALESCE(SUM(realized_pnl), 0) FROM trades").fetchone()[0], 2)
        pnl_src = round(sum(r.get("realized_pnl") or 0 for r in b["trades"]), 2)
        if pnl_db != pnl_src:
            problems.append(f"realised P&L {pnl_db} != {pnl_src}")
    if n_e:
        by_type = dict(con.execute("SELECT event_type, COUNT(*) FROM audit_events GROUP BY event_type").fetchall())
        if by_type != (counts.get("by_type") or {}):
            problems.append("event counts by type differ")
    con.close()
    return {"ok": not problems, "problems": problems, "trades": n_t, "audit_events": n_e}


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
    drill = restore_drill(name)
    text = (f"💾 Garud weekly backup: {c['trades']} trades, {c['audit_events']} events, {size / 1024:.0f} KB "
            "— saved for 90 days under Actions → 'Database backup (weekly)' → Artifacts\n"
            + ("✅ Restore drill OK: the file was loaded into a test database and every count matched."
               if drill["ok"] else "⚠️ Restore drill FAILED: " + "; ".join(drill["problems"])))
    print(text)
    print(json.dumps(c["by_type"], indent=1))
    send_telegram(text)
    return 0 if drill["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
