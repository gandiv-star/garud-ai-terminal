from dataclasses import dataclass
from datetime import datetime


@dataclass
class TradeRecord:
    internal_order_id: str
    symbol: str
    strategy_name: str
    strategy_version: str
    decision: str
    ai_score: float
    entry_price: float
    stop_price: float
    target_price: float | None
    quantity: int
    risk_amount: float
    regime: str
    sector: str
    timestamp: datetime
    broker_order_id: str | None = None
    exit_price: float | None = None
    exit_timestamp: datetime | None = None
    realized_pnl: float | None = None


@dataclass
class AuditEvent:
    timestamp: datetime
    event_type: str
    symbol: str | None
    payload: dict
