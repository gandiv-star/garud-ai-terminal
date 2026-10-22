"""Shared fakes for the Garud regression tests. Nothing here talks to a network, a broker
or the real database."""
import contextlib
import os
import socket
import types
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ROOT_FILE(rel: str) -> str:
    return os.path.join(ROOT, rel)
UTC = timezone.utc
V2 = "volatility_expansion_rule_v2_nifty50"

# Every variable that can switch live trading on or change its limits.
LIVE_VARS = ("TRADING_MODE", "LIVE_ORDERS_ENABLED", "LIVE_RULES", "LIVE_START_DATE", "LIVE_MAX_ORDER_VALUE",
             "LIVE_CAPITAL", "LIVE_MAX_OPEN", "LIVE_MAX_STOCK_PCT", "LIVE_DAILY_LOSS_LIMIT",
             "LIVE_MONTHLY_LOSS_LIMIT", "GARUD_KILL_SWITCH", "BROKER_ACCESS_TOKEN", "UPSTOX_SANDBOX_TOKEN",
             "UPSTOX_ANALYTICS_TOKEN", "DATABASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "RUN_SOURCE")


def clean_env() -> None:
    for k in LIVE_VARS:
        os.environ.pop(k, None)


@contextlib.contextmanager
def env(**values):
    """Temporarily set environment variables (value None = remove)."""
    old = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


LIVE_ON = dict(TRADING_MODE="CONTROLLED_LIVE", LIVE_ORDERS_ENABLED="YES", LIVE_RULES=V2,
               LIVE_START_DATE="2026-11-02", LIVE_MAX_ORDER_VALUE="25000")


_blocked = False


def block_network() -> None:
    """Any attempt to open a network connection raises — a test can never reach a broker."""
    global _blocked
    if _blocked:
        return

    def refuse(*args, **kwargs):
        raise RuntimeError("network access is blocked in tests")

    socket.socket.connect = refuse
    socket.socket.connect_ex = refuse
    socket.create_connection = refuse
    _blocked = True


class Ev:
    def __init__(self, event_type, payload, timestamp=None, symbol=None):
        self.event_type, self.payload = event_type, payload
        self.timestamp = timestamp or datetime(2026, 10, 18, 4, 0, tzinfo=UTC)
        self.symbol = symbol


class FakeDB:
    """Append-only audit log, newest first on read — like database.db.Database."""

    def __init__(self):
        self.ev = []

    def get_audit_events(self, event_type, limit=100):
        return [e for e in reversed(self.ev) if e.event_type == event_type][:limit]

    def save_audit_event(self, a):
        self.ev.append(Ev(a.event_type, a.payload, getattr(a, "timestamp", None), getattr(a, "symbol", None)))

    def add(self, event_type, payload):
        self.ev.append(Ev(event_type, payload))

    def of(self, event_type):
        return [e.payload for e in self.ev if e.event_type == event_type]


class FakeBroker:
    """Records orders; never connects anywhere."""

    def __init__(self, status=None, filled=0, holdings=None, funds=10_000_000.0):
        from brokers.base_broker import OrderStatus
        self.orders, self.cancelled, self.gtt_cancelled, self.gtts = [], [], [], []
        self.status = status or OrderStatus.PENDING
        self.filled, self.holdings, self.funds = filled, dict(holdings or {}), funds

    def get_funds(self):
        if isinstance(self.funds, Exception):
            raise self.funds
        return {"data": {"equity": {"available_margin": self.funds}}}

    def place_order(self, req):
        self.orders.append(req)
        return types.SimpleNamespace(broker_order_id=f"o{len(self.orders)}", raw_response={})

    def get_order_status(self, order_id):
        return types.SimpleNamespace(status=self.status, filled_quantity=self.filled)

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)

    def cancel_gtt(self, gtt_id):
        self.gtt_cancelled.append(gtt_id)

    def place_gtt_stop(self, symbol, qty, stop):
        self.gtts.append((symbol, qty, stop))
        return f"g{len(self.gtts)}"

    def get_positions(self):
        return {"data": [{"tradingsymbol": s, "quantity": q} for s, q in self.holdings.items()]}

    def get_holdings(self):
        return {"data": []}


def trade(symbol="TCS", price=1000.0, qty=17, rule=V2, entered=datetime(2026, 11, 2, 3, 45, tzinfo=UTC),
          stop=None):
    from database.models import TradeRecord
    return TradeRecord(f"{rule}-{symbol}-{entered:%Y%m%d}", symbol, rule, "x", "BUY", 0, price,
                       stop if stop is not None else price * 0.95, None, qty, 1000, "WEAK_BEAR", "", entered)


def bar(d: date, o, h, l, c, symbol="X", v=100000):
    from data.data_loader import Bar
    return Bar(symbol, datetime(d.year, d.month, d.day, 0, 0, tzinfo=IST), o, h, l, c, v)


def trading_days(start: date, n: int) -> list:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out
