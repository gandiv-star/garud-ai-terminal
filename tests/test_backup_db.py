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
