from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketEvent:
    symbol: str
    timestamp: datetime
    event_type: str
    sentiment: float  # -1.0 to 1.0
    materiality: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    summary: str
    source: str


class NewsEngine:
    def fetch_events(self, symbol: str, since: datetime) -> list[MarketEvent]:
        raise NotImplementedError
