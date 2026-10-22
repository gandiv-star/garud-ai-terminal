"""Weekly database backup — fake session, no database."""
import gzip
import json
import types
from datetime import datetime

from backtest import backup_db


def _cls(name, cols):
    return type(name, (), {"__table__": types.SimpleNamespace(columns=[types.SimpleNamespace(name=c) for c in cols]),
                           "id": 0})


class Query:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def order_by(self, *_):
        return self


class Session:
    def __init__(self, data):
        self.data = data

    def query(self, cls):
        return Query(self.data[cls])


def test_dump_and_write():
    T, E = _cls("T", ["internal_order_id", "timestamp"]), _cls("E", ["id", "event_type", "payload"])
    t = types.SimpleNamespace(internal_order_id="a", timestamp=datetime(2026, 10, 1, 4, 0))
    e1 = types.SimpleNamespace(id=1, event_type="MOM_NAV", payload={"value": 1})
    e2 = types.SimpleNamespace(id=2, event_type="RULE_ENTRY", payload={})
    b = backup_db.dump(Session({T: [t], E: [e1, e2]}), T, E)
    assert b["counts"] == {"trades": 1, "audit_events": 2, "by_type": {"MOM_NAV": 1, "RULE_ENTRY": 1}}
    assert b["trades"][0]["timestamp"] == "2026-10-01T04:00:00"
    import tempfile
    import os
    path = os.path.join(tempfile.mkdtemp(), "b.json.gz")
    assert backup_db.write(b, path) > 0
    assert json.loads(gzip.open(path).read())["counts"]["trades"] == 1


def _write(b):
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), "b.json.gz")
    backup_db.write(b, path)
    return path


def test_restore_drill_matches_and_detects_damage():
    T = _cls("T", ["internal_order_id", "realized_pnl", "timestamp"])
    E = _cls("E", ["id", "event_type", "payload"])
    trades = [types.SimpleNamespace(internal_order_id="a", realized_pnl=-100.5, timestamp=datetime(2026, 10, 1)),
              types.SimpleNamespace(internal_order_id="b", realized_pnl=None, timestamp=datetime(2026, 10, 2))]
    events = [types.SimpleNamespace(id=1, event_type="MOM_NAV", payload={"v": [1, 2]}),
              types.SimpleNamespace(id=2, event_type="RULE_ENTRY", payload={})]
    b = backup_db.dump(Session({T: trades, E: events}), T, E)
    ok = backup_db.restore_drill(_write(b))
    assert ok == {"ok": True, "problems": [], "trades": 2, "audit_events": 2}
    b["audit_events"].pop()                                  # a lost row must be caught
    b["trades"][1]["internal_order_id"] = "a"                # and a duplicate id
    bad = backup_db.restore_drill(_write(b))
    assert not bad["ok"] and any("audit_events" in p for p in bad["problems"])
    assert any("duplicate" in p for p in bad["problems"])


def test_restore_drill_empty_database():
    b = {"trades": [], "audit_events": [], "counts": {"trades": 0, "audit_events": 0, "by_type": {}}}
    assert backup_db.restore_drill(_write(b))["ok"]
