from dataclasses import dataclass
from statistics import stdev

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
        if len(bars) < 20:
            return FeatureSet(symbol=symbol)

        closes = [b.close for b in bars]
        volumes = [b.volume for b in bars]

        sma20 = sum(closes[-20:]) / 20
        price = closes[-1]
        trend_strength = (price - sma20) / sma20 * 100

        lookback = min(10, len(closes) - 1)
        momentum = (closes[-1] - closes[-1 - lookback]) / closes[-1 - lookback] * 100

        atr_period = min(14, len(bars) - 1)
        true_ranges = []
        for i in range(len(bars) - atr_period, len(bars)):
            high, low = bars[i].high, bars[i].low
            prev_close = bars[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        atr = sum(true_ranges) / len(true_ranges)

        daily_returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))
        ]
        recent_returns = daily_returns[-20:]
        volatility = stdev(recent_returns) * (252 ** 0.5) if len(recent_returns) > 1 else 0.0

        avg_volume_20 = sum(volumes[-20:]) / 20
        relative_volume = volumes[-1] / avg_volume_20 if avg_volume_20 > 0 else None

        prev_close = closes[-2]
        gap_pct = (bars[-1].open - prev_close) / prev_close * 100

        return FeatureSet(
            symbol=symbol,
            trend_strength=round(trend_strength, 4),
            momentum=round(momentum, 4),
            atr=round(atr, 4),
            volatility=round(volatility, 4),
            relative_volume=round(relative_volume, 4) if relative_volume else None,
            gap_pct=round(gap_pct, 4),
        )
