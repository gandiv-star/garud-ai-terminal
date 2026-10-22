"""Full restore drill — restore through Garud's Database API into a separate database, then check
integrity with the app's own readers. Fake in-memory database locally; on GitHub the same code also
runs against a real SQLite file through SQLAlchemy (second test)."""
import gzip
import json
import os
import tempfile
import types
from datetime import datetime

from backtest import backup_db, restore_drill as rd


class MemDB:
    def __init__(self):
        self.trades, self.events = {}, []

    def save_trade(self, t):
        self.trades[t.internal_order_id] = t

    def get_trades(self, limit=50):
        return sorted(self.trades.values(), key=lambda t: t.timestamp, reverse=True)[:limit]

    def save_audit_event(self, a):
        self.events.append(a)

    def get_audit_events(self, kind, limit=100):
        return [e for e in reversed(self.events) if e.event_type == kind][:limit]


def _backup():
    T = type("T", (), {"__table__": types.SimpleNamespace(columns=[types.SimpleNamespace(name=c) for c in (
        "internal_order_id", "symbol", "strategy_name", "strategy_version", "decision", "ai_score", "entry_price",
        "stop_price", "target_price", "quantity", "risk_amount", "regime", "sector", "timestamp", "broker_order_id",
        "exit_price", "exit_timestamp", "realized_pnl")]), "id": 0})
    E = type("E", (), {"__table__": types.SimpleNamespace(columns=[types.SimpleNamespace(name=c) for c in (
        "id", "timestamp", "event_type", "symbol", "payload")]), "id": 0})
    mk = lambda i, pnl: types.SimpleNamespace(  # noqa: E731
        internal_order_id=f"v2-X{i}-2026-10-0{i}", symbol=f"X{i}", strategy_name="volatility_expansion_rule_v2_nifty50",
        strategy_version="2026-09-28", decision="BUY", ai_score=0.0, entry_price=100.0 + i, stop_price=95.0,
        target_price=None, quantity=10, risk_amount=50.0, regime="WEAK_BEAR", sector="", timestamp=datetime(2026, 10, i, 4, 15),
        broker_order_id=None, exit_price=None if pnl is None else 101.0, exit_timestamp=None if pnl is None else datetime(2026, 10, i + 2, 10, 0),
        realized_pnl=pnl)
    trades = [mk(1, -120.5), mk(2, 300.0), mk(3, None)]
    events = [types.SimpleNamespace(id=1, timestamp=datetime(2026, 10, 5, 12, 0), event_type="PIPELINE_RUN", symbol=None,
                                    payload={"error_count": 0, "kill_switch": False}),
              types.SimpleNamespace(id=2, timestamp=datetime(2026, 10, 6, 12, 0), event_type="MOM_NAV", symbol=None,
                                    payload={"portfolio": "G", "date": "2026-11-02", "value": 100000.0}),
              types.SimpleNamespace(id=3, timestamp=datetime(2026, 10, 7, 12, 0), event_type="RULE_BENCHMARK", symbol=None,
                                    payload={"rule_id": "v2", "version": 1, "pf": 1.14})]

    class Q:
        def __init__(s, rows): s.rows = rows
        def all(s): return s.rows               # noqa: E704
        def order_by(s, *_): return s           # noqa: E704

    class S:
        def query(s, cls): return Q(trades if cls is T else events)   # noqa: E704
    b = backup_db.dump(S(), T, E)
    path = os.path.join(tempfile.mkdtemp(), "b.json.gz")
    backup_db.write(b, path)
    return path


def test_restore_and_integrity_in_memory():
    backup = rd.load(_backup())
    db = MemDB()
    assert rd.restore(backup, db) == {"trades": 3, "audit_events": 3}
    assert rd.integrity(backup, db) == []
    t = db.trades["v2-X1-2026-10-01"]
    assert isinstance(t.timestamp, datetime) and t.realized_pnl == -120.5
    db.events.pop()                                       # damage: a lost event must be caught
    assert any("RULE_BENCHMARK" in p for p in rd.integrity(backup, db))


def test_refuses_production_database():
    old = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = "postgresql://example/garud"
        assert rd.main([_backup()]) == 2
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        assert rd.main([_backup()]) == 2
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


def test_restore_into_real_sqlite_through_sqlalchemy():
    """Runs on GitHub (SQLAlchemy installed). Skipped silently where SQLAlchemy is unavailable."""
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        return
    from config.settings import Settings
    from database.db import Database
    path = os.path.join(tempfile.mkdtemp(), "restore_test.db")
    s = Settings()
    s.database_url = f"sqlite:///{path}"
    db = Database(s)
    db.connect()
    backup = rd.load(_backup())
    rd.restore(backup, db)
    assert rd.integrity(backup, db) == []
    assert len(db.get_trades(limit=100)) == 3 and db.get_audit_events("MOM_NAV")[0].payload["portfolio"] == "G"
