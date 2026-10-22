"""Full restore drill (audit item 4): loads a weekly backup into a SEPARATE, throw-away test database
through Garud's own database code, checks integrity, then starts the real Streamlit app on it.

Safety: refuses to run unless DATABASE_URL is a local SQLite file (never the production database).
Run by .github/workflows/backup_db.yml right after the weekly backup, with
DATABASE_URL=sqlite:///restore_test.db; the test file is discarded with the runner.
Usage: python backtest/restore_drill.py garud_backup_YYYYMMDD.json.gz [--app]
"""
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TRADE_TIME_FIELDS = ("timestamp", "exit_timestamp")


def _dt(v):
    if v is None or isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v))


def load(path: str) -> dict:
    with gzip.open(path, "rb") as f:
        return json.loads(f.read())


def restore(backup: dict, db) -> dict:
    """Writes every trade and audit event into `db` (Garud's Database API). Returns counts written."""
    from database.models import AuditEvent, TradeRecord
    fields = TradeRecord.__dataclass_fields__
    n_t = n_e = 0
    for row in backup.get("trades") or []:
        data = {k: (_dt(v) if k in TRADE_TIME_FIELDS else v) for k, v in row.items() if k in fields}
        db.save_trade(TradeRecord(**data))
        n_t += 1
    for row in sorted(backup.get("audit_events") or [], key=lambda r: r.get("id") or 0):
        payload = row.get("payload")
        if isinstance(payload, str):
            payload = json.loads(payload)
        db.save_audit_event(AuditEvent(timestamp=_dt(row["timestamp"]), event_type=row["event_type"],
                                       symbol=row.get("symbol"), payload=payload if payload is not None else {}))
        n_e += 1
    return {"trades": n_t, "audit_events": n_e}


def integrity(backup: dict, db, now: datetime | None = None) -> list:
    """Problems found after the restore (empty list = all good). Reads only through Garud's code."""
    import garud_health as gh
    import garud_research as gr
    from backtest import rule_report
    problems = []
    counts = backup.get("counts") or {}
    trades = db.get_trades(limit=10 ** 6)
    if len(trades) != counts.get("trades"):
        problems.append(f"trades {len(trades)} != backup {counts.get('trades')}")
    ids = [t.internal_order_id for t in trades]
    if len(ids) != len(set(ids)):
        problems.append("duplicate trade ids after restore")
    pnl_db = round(sum(t.realized_pnl or 0 for t in trades), 2)
    pnl_src = round(sum(r.get("realized_pnl") or 0 for r in backup.get("trades") or []), 2)
    if pnl_db != pnl_src:
        problems.append(f"realised P&L {pnl_db} != backup {pnl_src}")
    for kind, n in (counts.get("by_type") or {}).items():
        got = len(db.get_audit_events(kind, limit=10 ** 6))
        if got != n:
            problems.append(f"{kind}: {got} != backup {n}")
    for t in trades:
        if t.timestamp is None or t.entry_price is None or t.quantity is None:
            problems.append(f"trade {t.internal_order_id} incomplete")
            break
    try:                                    # the app's own readers must work on the restored data
        rule_report.stored_benchmarks(db)
        gr.latest_studies(db)
        res = gh.run_db_checks(lambda: db, now or datetime.now(gh.IST))
        if res["db"].status == gh.BAD:
            problems.append(f"health check: {res['db'].detail}")
    except Exception as e:
        problems.append(f"app readers failed: {type(e).__name__}: {str(e)[:160]}")
    return problems


def app_starts(timeout: int = 240) -> tuple[bool, str]:
    """Runs the real Streamlit app (home screen) headless on the restored database."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=timeout)
    at.run()
    if at.exception:
        return False, "; ".join(str(getattr(e, "message", e))[:200] for e in at.exception)
    text = " ".join(str(m.value) for m in at.markdown)
    if "GARUD" not in text:
        return False, "home screen did not render the GARUD header"
    if "આ સ્ક્રીન લોડ ન થઈ" in text:
        return False, "home screen shows a load error"
    return True, "home screen rendered"


def main(argv: list) -> int:
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("sqlite:///") or url.startswith("sqlite:///:memory"):
        print("Refusing: the restore drill only writes to a local SQLite test file (DATABASE_URL=sqlite:///...).")
        return 2
    path = next((a for a in argv if a.endswith(".json.gz")), None)
    if not path:
        print("Usage: restore_drill.py <backup.json.gz> [--app]")
        return 2
    from config.settings import load_settings
    from database.db import Database
    from backtest.run_rule_paper import send_telegram
    backup = load(path)
    db = Database(load_settings())
    db.connect()
    if db.get_trades(limit=1) or db.get_audit_events("PIPELINE_RUN", limit=1):
        print("Refusing: the test database is not empty.")
        return 2
    wrote = restore(backup, db)
    problems = integrity(backup, db)
    app_ok, app_msg = (True, "not checked")
    if "--app" in argv:
        try:
            app_ok, app_msg = app_starts()
        except Exception as e:
            app_ok, app_msg = False, f"{type(e).__name__}: {str(e)[:200]}"
    ok = not problems and app_ok
    text = (f"{'✅' if ok else '⚠️'} Full restore drill ({datetime.now(timezone.utc):%d %b}): "
            f"{wrote['trades']} trades + {wrote['audit_events']} events restored into a throw-away test database"
            + (" · integrity OK" if not problems else " · PROBLEMS: " + "; ".join(problems[:5]))
            + f" · app: {app_msg}")
    print(text)
    send_telegram(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
