from dataclasses import dataclass

from data.data_loader import Bar


@dataclass
class FeatureSet:
    symbol: str
    trend_strength: float | None = None
    momentum: float | None = None
    atr: float | None = None
    volatility: float | None = None
    relative_volume: float | None = None
    gap_pct: float | None = None


class FeatureEngine:
    def compute(self, symbol: str, bars: list[Bar]) -> FeatureSet:
        raise NotImplementedError
