from dataclasses import dataclass
from datetime import datetime


@dataclass
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class DataLoader:
    def get_historical_bars(
        self, symbol: str, start: datetime, end: datetime, interval: str = "1d"
    ) -> list[Bar]:
        raise NotImplementedError

    def get_latest_quote(self, symbol: str) -> Bar:
        raise NotImplementedError

    def get_universe(self) -> list[str]:
        raise NotImplementedError

    def get_corporate_actions(self, symbol: str, start: datetime, end: datetime) -> list[dict]:
        raise NotImplementedError
